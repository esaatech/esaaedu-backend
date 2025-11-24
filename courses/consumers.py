"""
WebSocket consumers for board synchronization
Handles real-time collaboration for tldraw boards in classrooms
"""
import json
import logging
import time
import asyncio
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from firebase_admin import auth
import firebase_admin
from .models import Classroom, Board, BoardPage

logger = logging.getLogger(__name__)
User = get_user_model()


def ensure_firebase_initialized():
    """Ensure Firebase is initialized before use"""
    if not firebase_admin._apps:
        try:
            from backend.settings import initialize_firebase
            initialize_firebase()
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            return False
    return True


@database_sync_to_async
def verify_firebase_token(token):
    """Verify Firebase ID token and return decoded token"""
    if not ensure_firebase_initialized():
        raise ValueError("Firebase not initialized")
    
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise ValueError("Invalid authentication token")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise ValueError(f"Authentication failed: {e}")


@database_sync_to_async
def get_or_create_user(decoded_token):
    """Get or create Django user from Firebase token"""
    firebase_uid = decoded_token.get('uid')
    email = decoded_token.get('email')
    
    if not firebase_uid or not email:
        raise ValueError("Invalid token: missing required fields")
    
    try:
        user = User.objects.get(firebase_uid=firebase_uid)
    except User.DoesNotExist:
        name = decoded_token.get('name', '')
        name_parts = name.split(' ', 1) if name else ['', '']
        
        user = User.objects.create_user(
            firebase_uid=firebase_uid,
            email=email,
            first_name=name_parts[0],
            last_name=name_parts[1] if len(name_parts) > 1 else '',
            username=email,
            role=User.Role.STUDENT
        )
        logger.info(f"Created new user via WebSocket: {email}")
    
    return user


@database_sync_to_async
def get_classroom_and_validate_access(classroom_id, user):
    """
    Get classroom and validate user has access
    
    Args:
        classroom_id: UUID of the classroom
        user: Django user instance
        
    Returns:
        Classroom: Classroom instance if found and user has access
        
    Raises:
        Classroom.DoesNotExist: If classroom not found
        PermissionError: If user doesn't have access
    """
    try:
        classroom = Classroom.objects.select_related('class_instance', 'class_instance__teacher').get(id=classroom_id)
    except Classroom.DoesNotExist:
        raise Classroom.DoesNotExist(f"Classroom {classroom_id} not found")
    
    # Check access permissions
    if user.role == 'teacher':
        # Teacher must own the class
        if classroom.class_instance.teacher != user:
            raise PermissionError(f"User {user.email} does not own classroom {classroom_id}")
    elif user.role == 'student':
        # Student must be enrolled in the class
        if user not in classroom.class_instance.students.all():
            raise PermissionError(f"User {user.email} is not enrolled in classroom {classroom_id}")
    else:
        raise PermissionError(f"Invalid user role: {user.role}")
    
    return classroom


@database_sync_to_async
def get_or_create_board(classroom, user):
    """Get or create Board for classroom"""
    board, created = Board.objects.get_or_create(
        classroom=classroom,
        defaults={
            'created_by': user,
            'title': f"{classroom.class_instance.name} Board"
        }
    )
    # Ensure default page exists
    if created or not board.pages.exists():
        board.get_or_create_default_page()
    return board


@database_sync_to_async
def get_current_page_state(board):
    """Get current page state"""
    page = board.get_current_page()
    if page:
        return {
            'page_id': str(page.id),
            'page_name': page.page_name,
            'state': page.state,
            'version': page.version
        }
    return None


@database_sync_to_async
def save_page_state(board, page_id, state, user):
    """Save page state (auto-save)"""
    try:
        page = BoardPage.objects.get(id=page_id, board=board)
        page.state = state
        page.last_updated_by = user
        page.increment_version()
        page.save(update_fields=['state', 'last_updated_by', 'version', 'updated_at'])
        return True
    except BoardPage.DoesNotExist:
        logger.error(f"Page {page_id} not found for board {board.id}")
        return False
    except Exception as e:
        logger.error(f"Error saving page state: {e}", exc_info=True)
        return False


class BoardSyncConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for tldraw board synchronization
    Handles real-time collaboration between teacher and students
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.classroom = None
        self.board = None
        self.current_page = None
        self.authenticated = False
        self.room_group_name = None
        self.last_activity = None
        self.heartbeat_task = None
        self.idle_timeout_task = None
        self.auto_save_task = None
        self.pending_save_changes = None
        self.last_save_time = None
        self.IDLE_TIMEOUT = 30 * 60  # 30 minutes of inactivity
        self.HEARTBEAT_INTERVAL = 30  # Send ping every 30 seconds
        self.AUTO_SAVE_DELAY = 5  # Auto-save after 5 seconds of inactivity
    
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Extract classroom_id from URL
            kwargs = self.scope.get('url_route', {}).get('kwargs', {})
            classroom_id_str = kwargs.get('classroom_id')
            
            if not classroom_id_str:
                logger.error("Classroom ID not found in URL")
                await self.close(code=4004)
                return
            
            try:
                classroom_id = uuid.UUID(classroom_id_str)
            except ValueError:
                logger.error(f"Invalid classroom ID format: {classroom_id_str}")
                await self.close(code=4004)
                return
            
            # Accept connection first
            await self.accept()
            logger.info(f"BoardSyncConsumer connection opened for classroom: {classroom_id}")
            
            # Store classroom_id for later authentication
            self.classroom_id = classroom_id
            
            # Send welcome message
            await self.send_json({
                'type': 'connected',
                'message': 'WebSocket connected. Please authenticate.',
                'classroom_id': str(classroom_id)
            })
            
        except Exception as e:
            logger.error(f"Error in BoardSyncConsumer connect: {e}", exc_info=True)
            try:
                await self.close()
            except:
                pass
            raise
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"BoardSyncConsumer connection closed: {close_code}, user: {self.user.email if self.user else 'unknown'}")
        
        # Cancel heartbeat and timeout tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.idle_timeout_task:
            self.idle_timeout_task.cancel()
        
        # Leave room group
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        
        # Cleanup resources
        self.user = None
        self.classroom = None
        self.authenticated = False
        self.room_group_name = None
    
    async def receive(self, text_data=None, bytes_data=None):
        """Handle messages from client"""
        try:
            # Handle text data
            if text_data:
                data = json.loads(text_data)
            elif bytes_data:
                if isinstance(bytes_data, bytes):
                    text_data = bytes_data.decode('utf-8')
                elif isinstance(bytes_data, tuple):
                    text_data = bytes_data[0].decode('utf-8') if isinstance(bytes_data[0], bytes) else str(bytes_data[0])
                else:
                    text_data = str(bytes_data)
                data = json.loads(text_data)
            else:
                await self.send_error("No data received")
                return
            
            message_type = data.get('type', '')
            
            # Handle ping/pong for heartbeat
            if message_type == 'pong':
                self._update_activity()
                return
            
            # Update activity on any message
            self._update_activity()
            
            # Handle authentication
            if message_type == 'auth':
                await self.handle_auth(data)
                return
            
            # Require authentication for other messages
            if not self.authenticated:
                await self.send_error("Authentication required. Please send 'auth' message first.")
                await self.close()
                return
            
            # Route to appropriate handler
            if message_type == 'board_update':
                await self.handle_board_update(data)
            elif message_type == 'presence_update':
                await self.handle_presence_update(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self.send_error(f"Internal error: {str(e)}")
    
    async def handle_auth(self, data):
        """Handle authentication message"""
        token = data.get('token')
        
        if not token:
            await self.send_error("Token is required for authentication")
            await self.close()
            return
        
        try:
            # Verify Firebase token
            decoded_token = await verify_firebase_token(token)
            
            # Get or create user
            self.user = await get_or_create_user(decoded_token)
            
            # Get classroom and validate access
            if not hasattr(self, 'classroom_id'):
                await self.send_error("Classroom ID is required")
                await self.close()
                return
            
            self.classroom = await get_classroom_and_validate_access(self.classroom_id, self.user)
            
            # Check if board is enabled
            if not self.classroom.board_enabled:
                await self.send_error("Board is not enabled for this classroom")
                await self.close()
                return
            
            # Get or create board
            self.board = await get_or_create_board(self.classroom, self.user)
            self.current_page = await get_current_page_state(self.board)
            
            # Check board permissions
            can_edit = self.board.can_user_edit(self.user)
            can_create_pages = self.board.can_user_create_pages(self.user)
            
            self.authenticated = True
            
            # Join room group
            self.room_group_name = f"board_{self.classroom_id}"
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Start heartbeat and idle timeout monitoring
            self.last_activity = time.time()
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self.idle_timeout_task = asyncio.create_task(self._idle_timeout_loop())
            
            # Send authentication success with board info
            await self.send_json({
                'type': 'auth_success',
                'message': 'Authentication successful',
                'classroom_id': str(self.classroom_id),
                'user_id': str(self.user.id),
                'user_role': self.user.role,
                'user_name': self.user.get_full_name() or self.user.email,
                'board': {
                    'id': str(self.board.id),
                    'title': self.board.title,
                    'can_edit': can_edit,
                    'can_create_pages': can_create_pages,
                    'view_only_mode': self.board.view_only_mode
                }
            })
            
            # Send initial board state if current page exists
            if self.current_page and self.current_page.get('state'):
                # Ensure state is properly formatted
                page_state = self.current_page['state']
                # If state is empty dict, send empty state
                if isinstance(page_state, dict) and len(page_state) > 0:
                    await self.send_json({
                        'type': 'board_state_sync',
                        'page_id': self.current_page['page_id'],
                        'page_name': self.current_page['page_name'],
                        'state': page_state,
                        'version': self.current_page['version']
                    })
            
            # Notify others in the room that user joined
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_joined',
                    'user_id': str(self.user.id),
                    'user_name': self.user.get_full_name() or self.user.email,
                    'user_role': self.user.role
                }
            )
            
            logger.info(f"User authenticated for board sync: {self.user.email}, classroom: {self.classroom.class_instance.name}, can_edit: {can_edit}")
            
        except ValueError as e:
            await self.send_error(f"Authentication failed: {str(e)}")
            await self.close()
        except PermissionError as e:
            await self.send_error(f"Access denied: {str(e)}")
            await self.close()
        except Exception as e:
            logger.error(f"Auth error: {e}", exc_info=True)
            await self.send_error("Authentication error")
            await self.close()
    
    async def handle_board_update(self, data):
        """Handle board update from client - broadcast to others in room and trigger auto-save"""
        # Check if user can edit
        if not self.board.can_user_edit(self.user):
            await self.send_error("You do not have permission to edit this board")
            return
        
        changes = data.get('changes', {})
        presence = data.get('presence', {})
        # Extract page_id and full_state from presence or data
        page_id = data.get('page_id') or (presence.get('page_id') if isinstance(presence, dict) else None)
        full_state = data.get('full_state') or (presence.get('full_state') if isinstance(presence, dict) else None)
        
        # Count changes properly (changes is a dict with added/updated/removed keys)
        if isinstance(changes, dict):
            changes_count = len(changes.get('added', {})) + len(changes.get('updated', {})) + len(changes.get('removed', {}))
        else:
            changes_count = len(changes) if changes else 0
        
        if changes_count == 0:
            logger.debug(f"No changes to broadcast from {self.user.email}")
            return
        
        # Update activity for auto-save
        self.last_activity = time.time()
        
        # Store pending save data if provided
        if page_id and full_state:
            self.pending_save_changes = {
                'page_id': page_id,
                'state': full_state
            }
            # Cancel existing auto-save task
            if self.auto_save_task and not self.auto_save_task.done():
                self.auto_save_task.cancel()
            # Schedule new auto-save
            self.auto_save_task = asyncio.create_task(self._auto_save_page())
        
        # Broadcast to all users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'board_update',
                'changes': changes,
                'presence': presence,
                'from_user': str(self.user.id),
                'from_user_name': self.user.get_full_name() or self.user.email,
                'timestamp': time.time()
            }
        )
    
    async def handle_presence_update(self, data):
        """Handle presence update (cursor position, selection, etc.)"""
        presence = data.get('presence', {})
        
        # Broadcast presence to others in room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'presence_update',
                'presence': presence,
                'from_user': str(self.user.id),
                'from_user_name': self.user.get_full_name() or self.user.email,
                'timestamp': time.time()
            }
        )
    
    # Handler methods for group messages
    async def board_update(self, event):
        """Receive board update from room group"""
        # Note: We send to ALL consumers, including the sender
        # The frontend will filter out its own messages based on from_user or connection ID
        # This allows the same user on multiple browsers/devices to see each other's changes
        
        # Count changes properly (changes is a dict with added/updated/removed keys)
        changes = event.get('changes', {})
        changes_count = len(changes.get('added', {})) + len(changes.get('updated', {})) + len(changes.get('removed', {}))
        
        await self.send_json({
            'type': 'board_update',
            'changes': event['changes'],
            'presence': event.get('presence', {}),
            'from_user': event['from_user'],
            'from_user_name': event['from_user_name'],
            'timestamp': event['timestamp']
        })
    
    async def presence_update(self, event):
        """Receive presence update from room group"""
        # Don't send back to sender
        if event['from_user'] == str(self.user.id):
            return
        
        await self.send_json({
            'type': 'presence_update',
            'presence': event['presence'],
            'from_user': event['from_user'],
            'from_user_name': event['from_user_name'],
            'timestamp': event['timestamp']
        })
    
    async def user_joined(self, event):
        """Receive user joined notification"""
        # Don't send back to sender
        if event['user_id'] == str(self.user.id):
            return
        
        await self.send_json({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'user_role': event['user_role']
        })
    
    async def user_left(self, event):
        """Receive user left notification"""
        await self.send_json({
            'type': 'user_left',
            'user_id': event['user_id'],
            'user_name': event['user_name']
        })
    
    async def send_json(self, data):
        """Send JSON message to client"""
        await self.send(text_data=json.dumps(data))
    
    async def send_error(self, message):
        """Send error message to client"""
        await self.send_json({
            'type': 'error',
            'message': message
        })
    
    def _update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()
    
    async def _heartbeat_loop(self):
        """Send periodic ping to keep connection alive and detect dead connections"""
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                if not self.authenticated:
                    break
                
                try:
                    await self.send_json({
                        'type': 'ping',
                        'timestamp': time.time()
                    })
                except Exception as e:
                    logger.warning(f"Heartbeat ping failed, closing connection: {e}")
                    await self.close()
                    break
        except asyncio.CancelledError:
            logger.debug("Heartbeat task cancelled")
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}")
    
    async def _idle_timeout_loop(self):
        """Close connection if idle for too long"""
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute
                
                if not self.authenticated:
                    break
                
                if self.last_activity:
                    idle_time = time.time() - self.last_activity
                    if idle_time > self.IDLE_TIMEOUT:
                        logger.info(f"Closing idle board connection (idle for {idle_time:.0f}s): {self.user.email if self.user else 'unknown'}")
                        await self.send_json({
                            'type': 'idle_timeout',
                            'message': 'Connection closed due to inactivity'
                        })
                        await self.close(code=4000)
                        break
        except asyncio.CancelledError:
            logger.debug("Idle timeout task cancelled")
        except Exception as e:
            logger.error(f"Idle timeout loop error: {e}")
    
    async def _auto_save_page(self):
        """Auto-save page state after delay"""
        try:
            # Wait for auto-save delay
            await asyncio.sleep(self.AUTO_SAVE_DELAY)
            
            # Check if still authenticated and have pending changes
            if not self.authenticated or not self.pending_save_changes:
                return
            
            # Check if enough time has passed since last activity
            if self.last_activity:
                time_since_activity = time.time() - self.last_activity
                if time_since_activity < self.AUTO_SAVE_DELAY:
                    # More activity happened, reschedule
                    return
            
            # Save the page state
            if self.board and self.user:
                success = await save_page_state(
                    self.board,
                    self.pending_save_changes['page_id'],
                    self.pending_save_changes['state'],
                    self.user
                )
                
                if success:
                    self.last_save_time = time.time()
                    logger.debug(f"Auto-saved board page {self.pending_save_changes['page_id']} for user {self.user.email}")
                    # Clear pending changes after successful save
                    self.pending_save_changes = None
                else:
                    logger.warning(f"Failed to auto-save board page {self.pending_save_changes['page_id']}")
                    
        except asyncio.CancelledError:
            logger.debug("Auto-save task cancelled")
        except Exception as e:
            logger.error(f"Auto-save error: {e}", exc_info=True)

