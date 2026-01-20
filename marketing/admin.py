from django.contrib import admin
from django.utils.html import format_html, escapejs
from django.urls import reverse
from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.core.files.storage import default_storage
import logging
from courses.models import Course
from .models import Program

logger = logging.getLogger(__name__)


class JSONListWidget(forms.Widget):
    """
    Custom widget for JSONField that provides a user-friendly interface
    with add/remove functionality for list items.
    """
    template_name = 'admin/marketing/json_list_widget.html'
    
    def __init__(self, attrs=None, placeholder='Enter item and click Add'):
        self.placeholder = placeholder
        super().__init__(attrs)
    
    def format_value(self, value):
        """Convert JSON list to string for JavaScript."""
        import json
        
        # Handle None or empty values
        if value is None or value == '':
            return '[]'
        
        # If it's already a string (JSON), validate and return
        if isinstance(value, str):
            try:
                # Validate it's valid JSON
                parsed = json.loads(value)
                # Ensure it's a list
                if isinstance(parsed, list):
                    return json.dumps(parsed)
                else:
                    return '[]'
            except (json.JSONDecodeError, TypeError):
                return '[]'
        
        # If it's already a list/dict, convert to JSON string
        if isinstance(value, (list, dict)):
            try:
                return json.dumps(value)
            except (TypeError, ValueError):
                return '[]'
        
        # Fallback
        return '[]'
    
    def value_from_datadict(self, data, files, name):
        """Get JSON string from hidden input (Django JSONField expects a string)."""
        import json
        value = data.get(name, '[]')
        # Return as string - Django's JSONField will parse it
        if not value:
            return '[]'
        # If it's already a string, validate and return it
        if isinstance(value, str):
            try:
                # Validate it's valid JSON
                json.loads(value)
                return value
            except (json.JSONDecodeError, TypeError):
                return '[]'
        # If it's already a list/dict, convert to JSON string
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return '[]'
    
    def render(self, name, value, attrs=None, renderer=None):
        """Render the widget with custom HTML."""
        if attrs is None:
            attrs = {}
        
        # Get the formatted value
        json_value = self.format_value(value)
        # For data attribute, we need to escape HTML entities
        # JSON uses double quotes, so we'll use single quotes for the HTML attribute
        import html
        escaped_json_attr = html.escape(json_value, quote=False)  # Don't escape quotes, we'll use single quotes
        widget_id = attrs.get('id', f'id_{name}')
        escaped_placeholder = escapejs(self.placeholder)
        
        # Create the HTML structure
        html = f'''
        <div class="json-list-widget" id="{widget_id}_container">
            <div class="json-list-input-group">
                <input 
                    type="text" 
                    id="{widget_id}_input" 
                    class="json-list-input" 
                    placeholder="{escaped_placeholder}"
                    autocomplete="off"
                />
                <button 
                    type="button" 
                    class="json-list-add-btn" 
                    id="{widget_id}_add"
                    title="Add item"
                >
                    <span class="json-list-add-icon">+</span>
                </button>
            </div>
            <div class="json-list-items" id="{widget_id}_items">
                <!-- Items will be added here dynamically -->
            </div>
            <input 
                type="hidden" 
                name="{name}" 
                id="{widget_id}" 
                value='{escaped_json_attr}'
                data-initial-value='{escaped_json_attr}'
            />
        </div>
        <script>
        (function() {{
            const container = document.getElementById('{widget_id}_container');
            const input = document.getElementById('{widget_id}_input');
            const addBtn = document.getElementById('{widget_id}_add');
            const itemsContainer = document.getElementById('{widget_id}_items');
            const hiddenInput = document.getElementById('{widget_id}');
            
            let items = [];
            try {{
                // Read the initial value from data attribute (safer than parsing escaped string)
                const initialValue = hiddenInput.getAttribute('data-initial-value');
                if (initialValue && initialValue.trim() && initialValue !== '[]') {{
                    const parsed = JSON.parse(initialValue);
                    // Ensure it's an array
                    if (Array.isArray(parsed)) {{
                        items = parsed;
                    }} else {{
                        items = [];
                    }}
                }} else {{
                    // Also try reading from value attribute as fallback
                    const jsonValue = hiddenInput.value;
                    if (jsonValue && jsonValue.trim() && jsonValue !== '[]') {{
                        const parsed = JSON.parse(jsonValue);
                        if (Array.isArray(parsed)) {{
                            items = parsed;
                        }}
                    }}
                }}
            }} catch (e) {{
                console.error('Error parsing JSON for {widget_id}:', e);
                console.error('Initial value:', hiddenInput.getAttribute('data-initial-value'));
                console.error('Hidden input value:', hiddenInput.value);
                items = [];
            }}
            
            function updateHiddenInput() {{
                hiddenInput.value = JSON.stringify(items);
            }}
            
            function renderItems() {{
                itemsContainer.innerHTML = '';
                if (items.length === 0) {{
                    itemsContainer.innerHTML = '<div style="padding: 12px; text-align: center; color: #999; font-style: italic;">No items added yet. Add items using the input above.</div>';
                    updateHiddenInput();
                    return;
                }}
                items.forEach((item, index) => {{
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'json-list-item';
                    const itemText = document.createElement('span');
                    itemText.className = 'json-list-item-text';
                    itemText.textContent = item;
                    const removeBtn = document.createElement('button');
                    removeBtn.type = 'button';
                    removeBtn.className = 'json-list-remove-btn';
                    removeBtn.setAttribute('data-index', index);
                    removeBtn.title = 'Remove';
                    const removeIcon = document.createElement('span');
                    removeIcon.textContent = '×';
                    removeBtn.appendChild(removeIcon);
                    itemDiv.appendChild(itemText);
                    itemDiv.appendChild(removeBtn);
                    itemsContainer.appendChild(itemDiv);
                }});
                updateHiddenInput();
            }}
            
            function addItem() {{
                const value = input.value.trim();
                if (!value) {{
                    return;
                }}
                if (items.includes(value)) {{
                    alert('This item already exists!');
                    return;
                }}
                items.push(value);
                input.value = '';
                input.focus();
                renderItems();
            }}
            
            function removeItem(index) {{
                if (index >= 0 && index < items.length) {{
                    items.splice(index, 1);
                    renderItems();
                }}
            }}
            
            addBtn.addEventListener('click', addItem);
            input.addEventListener('keypress', function(e) {{
                if (e.key === 'Enter') {{
                    e.preventDefault();
                    addItem();
                }}
            }});
            
            itemsContainer.addEventListener('click', function(e) {{
                const removeBtn = e.target.closest('.json-list-remove-btn');
                if (removeBtn) {{
                    const index = parseInt(removeBtn.getAttribute('data-index'));
                    removeItem(index);
                }}
            }});
            
            // Initial render (with small delay to ensure DOM is ready)
            setTimeout(function() {{
                renderItems();
            }}, 50);
        }})();
        </script>
        '''
        return mark_safe(html)


class ProgramAdminForm(forms.ModelForm):
    """
    Custom admin form for Program model.
    - Category field is a dropdown of available categories
    - JavaScript enforces mutual exclusivity between category and courses
    - JSONField widgets for easier editing of feature lists
    - Slug field is optional (auto-generated from name)
    """
    
    category = forms.ChoiceField(
        required=False,
        choices=[],
        help_text="Select a category to include all courses in that category (mutually exclusive with courses field)"
    )
    
    
    class Meta:
        model = Program
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'promotion_message': forms.Textarea(attrs={'rows': 3}),
            'hero_features': JSONListWidget(placeholder='Enter feature (e.g., "Canadian Curriculum") and click +'),
            'hero_value_propositions': JSONListWidget(placeholder='Enter value proposition (e.g., "Build confidence. Improve results.") and click +'),
            'program_overview_features': JSONListWidget(placeholder='Enter feature (e.g., "Live Classes") and click +'),
            'trust_strip_features': JSONListWidget(placeholder='Enter trust indicator (e.g., "Live Classes") and click +'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get distinct categories from published courses
        categories = Course.objects.filter(
            status='published'
        ).values_list('category', flat=True).distinct().order_by('category')
        
        # Create choices list with empty option
        category_choices = [('', '---------')] + [(cat, cat) for cat in categories if cat]
        self.fields['category'].choices = category_choices
        
        # Set initial value if editing existing program
        if self.instance and self.instance.pk and self.instance.category:
            self.initial['category'] = self.instance.category
        
        # Make slug optional in the form (will be auto-generated)
        self.fields['slug'].required = False
        
        # Add help text for JSON fields
        self.fields['hero_features'].help_text = "Enter one feature per line. These will be displayed in the hero section (e.g., 'Canadian Curriculum | Small Groups | Real Results')."
        self.fields['hero_value_propositions'].help_text = "Enter one value proposition per line. These will be displayed as marketing slogans in the hero section."
        self.fields['program_overview_features'].help_text = "Enter one feature per line. These will be displayed with checkmarks in the Program Overview section."
        self.fields['trust_strip_features'].help_text = "Enter one trust indicator per line. These will be displayed with checkmarks in the Trust Strip section."
    
    def clean_slug(self):
        """Auto-generate slug from name if not provided."""
        from django.utils.text import slugify
        
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        
        # If slug is not provided, generate from name
        if not slug and name:
            slug = slugify(name)
            # Ensure uniqueness
            original_slug = slug
            counter = 1
            while Program.objects.filter(slug=slug).exclude(pk=self.instance.pk if self.instance else None).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1
        
        return slug
    
    def clean_hero_media(self):
        """Handle hero_media field clearing."""
        # Get the value from cleaned_data (already processed by Django's FileField)
        hero_media = self.cleaned_data.get('hero_media')
        
        # When clear checkbox is checked, Django sets FileField to False
        # We need to convert this to None/empty to actually clear the field
        if hero_media is False:
            # Clear checkbox was checked - return empty string to clear the field
            # Django FileField accepts empty string to clear
            return ''
        
        return hero_media
    
    def clean(self):
        """Validate that either category OR courses is set (but not both)."""
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        
        # Only validate if this is a form submission (has data attribute)
        if not (hasattr(self, 'data') and self.data):
            return cleaned_data
        
        has_courses = False
        
        # Check raw POST data first - Django's filter_horizontal sends courses as a list
        # This is the most reliable way to check if courses were selected
        if 'courses' in self.data:
            courses_data = self.data.getlist('courses')
            # Filter out empty strings, None values, and whitespace-only strings
            courses_data = [c for c in courses_data if c and str(c).strip()]
            has_courses = len(courses_data) > 0
        
        # Also check cleaned_data - Django might have already processed it
        # For ManyToMany fields, cleaned_data might have the queryset/list
        if not has_courses and 'courses' in cleaned_data:
            courses_value = cleaned_data.get('courses')
            if courses_value:
                # ManyToMany fields can be querysets, lists, or empty
                try:
                    # Try to get length if it's iterable
                    if hasattr(courses_value, '__iter__') and not isinstance(courses_value, str):
                        course_list = list(courses_value)
                        has_courses = len(course_list) > 0
                    else:
                        has_courses = bool(courses_value)
                except (TypeError, AttributeError):
                    has_courses = bool(courses_value)
        
        # Also check if instance has courses (for existing programs being edited)
        # This handles the case where we're editing and courses are already saved
        # and user hasn't changed them
        if not has_courses and self.instance and self.instance.pk:
            has_courses = self.instance.courses.exists()
        
        has_category = bool(category and category.strip())
        
        # Validation rules
        if has_category and has_courses:
            raise ValidationError({
                'category': 'Cannot set both category and courses. Choose one.',
                'courses': 'Cannot set both category and courses. Choose one.'
            })
        
        if not has_category and not has_courses:
            raise ValidationError({
                'category': 'Either category or courses must be set.',
                'courses': 'Either category or courses must be set.'
            })
        
        return cleaned_data


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """
    Admin interface for Program model.
    """
    form = ProgramAdminForm
    
    class Media:
        js = ('admin/js/program_admin.js',)
        css = {
            'all': ('admin/css/program_admin.css', 'admin/css/json_list_widget.css',)
        }
    
    list_display = [
        'name',
        'slug',
        'category',
        'course_count_display',
        'is_active',
        'discount_enabled',
        'created_at',
        'seo_url_display'
    ]
    list_filter = [
        'is_active',
        'discount_enabled',
        'hero_media_type',
        'category',
        'created_at'
    ]
    search_fields = [
        'name',
        'slug',
        'category',
        'description'
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'seo_url_display',
        'marketing_url_display',
        'course_count_display',
        'hero_media_url'  # Auto-generated from hero_media file
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'marketing_url_display')
        }),
        ('Hero Section', {
            'description': 'Hero section with background media and text overlay. Drag and drop or click to upload an image (jpg, png, gif, webp) or video (mp4, webm) file - it will be automatically uploaded to GCS when you save. Media type is auto-detected from file extension. Media is used as background, text is displayed on top.',
            'fields': (
                'hero_media',
                'hero_media_url',
                'hero_media_type',
                'hero_title',
                'hero_subtitle',
                'hero_features',
                'hero_value_propositions',
            )
        }),
        ('Program Overview', {
            'description': 'Features displayed in the Program Overview section with checkmarks.',
            'fields': ('program_overview_features',)
        }),
        ('Trust Strip', {
            'description': 'Trust indicators displayed in the Trust Strip section (typically shown in hero area).',
            'fields': ('trust_strip_features',)
        }),
        ('Call to Action', {
            'fields': ('cta_text',)
        }),
        ('Course Selection (Choose One)', {
            'description': 'Either select a category OR specific courses, but not both.',
            'fields': ('category', 'courses')
        }),
        ('Discount & Promotion', {
            'fields': (
                'discount_enabled',
                'promotion_message',
                'promo_code'
            )
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'seo_url_display', 'course_count_display'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['courses']
    
    def course_count_display(self, obj):
        """Display course count with link to courses."""
        count = obj.course_count
        if count > 0:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                reverse('admin:courses_course_changelist') + f'?programs__id__exact={obj.id}',
                f'{count} course(s)'
            )
        return '0 courses'
    course_count_display.short_description = 'Courses'
    
    def marketing_url_display(self, obj):
        """Display marketing URL (same as SEO URL) - shown in Basic Information section."""
        if obj.slug:
            url = f"https://www.sbtyacedemy.com/programs/{obj.slug}"
            return format_html(
                '<div style="display: flex; align-items: center; gap: 8px; margin-top: 8px;">'
                '<strong style="min-width: 120px;">Marketing URL:</strong>'
                '<input type="text" value="{}" readonly style="flex: 1; padding: 8px; border: 2px solid #007cba; border-radius: 4px; font-family: monospace; font-size: 14px;" id="marketing-url-{}">'
                '<button type="button" onclick="navigator.clipboard.writeText(\'{}\').then(() => {{ const btn = event.target; btn.textContent = \'Copied!\'; setTimeout(() => btn.textContent = \'Copy\', 2000); }})" '
                'style="padding: 8px 16px; background: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">Copy</button>'
                '</div>',
                url,
                obj.id if obj.id else 'new',
                url
            )
        return format_html('<em style="color: #999;">Slug will be auto-generated from name</em>')
    marketing_url_display.short_description = 'Marketing URL'
    
    def seo_url_display(self, obj):
        """Display SEO URL with copy button (shown in Metadata section)."""
        if obj.slug:
            url = f"https://www.sbtyacedemy.com/programs/{obj.slug}"
            return format_html(
                '<div style="display: flex; align-items: center; gap: 8px;">'
                '<input type="text" value="{}" readonly style="flex: 1; padding: 4px; border: 1px solid #ddd; border-radius: 4px;" id="seo-url-{}">'
                '<button type="button" onclick="navigator.clipboard.writeText(\'{}\').then(() => alert(\'URL copied!\'))" '
                'style="padding: 4px 8px; background: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer;">Copy</button>'
                '</div>',
                url,
                obj.id,
                url
            )
        return '-'
    seo_url_display.short_description = 'SEO URL'
    
    def save_model(self, request, obj, form, change):
        """Override save - validation happens in form.clean()."""
        # Get old file info before save
        old_hero_media_name = None
        if change and obj.pk:
            try:
                old_obj = Program.objects.get(pk=obj.pk)
                old_hero_media_name = old_obj.hero_media.name if old_obj.hero_media else None
            except Program.DoesNotExist:
                pass
        
        # Check if hero_media clear checkbox is checked
        # Django admin sends 'hero_media-clear' in POST data when checkbox is checked
        is_clearing = False
        if hasattr(form, 'data') and form.data:
            is_clearing = form.data.get('hero_media-clear') == 'on'
        
        # Save the model first (Django handles the clear checkbox automatically)
        super().save_model(request, obj, form, change)
        
        # Refresh from database to get the actual saved state
        obj.refresh_from_db()
        
        # After save, check what actually happened
        new_hero_media_name = obj.hero_media.name if obj.hero_media else None
        
        # If file was cleared or removed, delete from GCS and clear URL
        if is_clearing or (old_hero_media_name and not new_hero_media_name):
            # File was cleared - delete from GCS
            if old_hero_media_name:
                try:
                    if default_storage.exists(old_hero_media_name):
                        default_storage.delete(old_hero_media_name)
                        logger.info(f"Deleted hero_media from GCS (cleared): {old_hero_media_name}")
                except Exception as e:
                    logger.error(f"Error deleting hero_media from GCS: {e}")
            
            # Clear the URL field
            Program.objects.filter(pk=obj.pk).update(hero_media_url=None)
            
            # If clearing, ensure the field is actually cleared in the database
            # The form's clean_hero_media should have converted False to '', but let's ensure it
            if is_clearing:
                # Refresh to get current state
                obj.refresh_from_db()
                # If field still has a value, force clear it using direct database update
                # For FileField, empty string clears it
                if obj.hero_media:
                    Program.objects.filter(pk=obj.pk).update(hero_media='')
                    obj.refresh_from_db()
        # If file was replaced, delete old file
        elif old_hero_media_name and new_hero_media_name and old_hero_media_name != new_hero_media_name:
            try:
                if default_storage.exists(old_hero_media_name):
                    default_storage.delete(old_hero_media_name)
                    logger.info(f"Deleted old hero_media from GCS (replaced): {old_hero_media_name}")
            except Exception as e:
                logger.error(f"Error deleting old hero_media from GCS: {e}")
        
        # Update hero_media_url after save (if new file exists)
        if obj.hero_media:
            try:
                obj.hero_media_url = default_storage.url(obj.hero_media.name)
                Program.objects.filter(pk=obj.pk).update(hero_media_url=obj.hero_media_url)
            except Exception as e:
                logger.error(f"Error generating hero_media_url: {e}")
    
    def save_related(self, request, form, formsets, change):
        """Save related objects (like ManyToMany courses)."""
        super().save_related(request, form, formsets, change)
    
    def delete_model(self, request, obj):
        """Override delete to remove hero_media from GCS."""
        # Delete hero_media file from GCS
        if obj.hero_media:
            try:
                if default_storage.exists(obj.hero_media.name):
                    default_storage.delete(obj.hero_media.name)
                    logger.info(f"Deleted hero_media from GCS: {obj.hero_media.name}")
            except Exception as e:
                logger.error(f"Error deleting hero_media from GCS: {e}")
        
        super().delete_model(request, obj)
    
    def get_form(self, request, obj=None, **kwargs):
        """Return custom form with dynamic category choices."""
        form = super().get_form(request, obj, **kwargs)
        return form

