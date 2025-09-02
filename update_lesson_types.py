#!/usr/bin/env python
"""
Script to update existing ClassEvent records to set lesson_type to 'live' 
for events that have meeting details (indicating they are live lessons).
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'little_learners_tech.settings')
django.setup()

from courses.models import ClassEvent
from django.db import transaction
from django.db import models

def update_lesson_types():
    """
    Update ClassEvent records to set lesson_type to 'live' for events with meeting details.
    """
    print("🔍 Starting lesson type update process...")
    
    # Get all ClassEvent records
    total_events = ClassEvent.objects.count()
    print(f"📊 Total ClassEvent records: {total_events}")
    
    # Find events that should be marked as live lessons
    live_candidates = ClassEvent.objects.filter(
        meeting_link__isnull=False,
        meeting_link__gt=''
    ).exclude(lesson_type='live')
    
    live_candidates_count = live_candidates.count()
    print(f"🎯 Events with meeting details (candidates for live): {live_candidates_count}")
    
    if live_candidates_count == 0:
        print("✅ No events need updating - all live lessons are already marked correctly!")
        return
    
    # Show some examples of what will be updated
    print("\n📋 Examples of events that will be updated:")
    for event in live_candidates[:5]:  # Show first 5 examples
        print(f"  - {event.title} (Class: {event.class_instance.name})")
        print(f"    Meeting Link: {event.meeting_link}")
        print(f"    Current lesson_type: {event.lesson_type}")
        print()
    
    # Confirm before proceeding
    response = input("Do you want to proceed with updating these events? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Update cancelled.")
        return
    
    # Update the records
    try:
        with transaction.atomic():
            updated_count = live_candidates.update(lesson_type='live')
            print(f"✅ Successfully updated {updated_count} events to lesson_type='live'")
            
            # Verify the update
            live_lessons = ClassEvent.objects.filter(lesson_type='live').count()
            print(f"📊 Total live lessons after update: {live_lessons}")
            
    except Exception as e:
        print(f"❌ Error updating records: {str(e)}")
        return
    
    # Show summary of all lesson types
    print("\n📊 Final lesson type distribution:")
    lesson_type_counts = ClassEvent.objects.values('lesson_type').annotate(
        count=models.Count('id')
    ).order_by('lesson_type')
    
    for item in lesson_type_counts:
        print(f"  - {item['lesson_type']}: {item['count']} events")

def show_current_lesson_types():
    """
    Show current distribution of lesson types.
    """
    print("\n🔍 Current lesson type distribution:")
    lesson_type_counts = ClassEvent.objects.values('lesson_type').annotate(
        count=models.Count('id')
    ).order_by('lesson_type')
    
    for item in lesson_type_counts:
        print(f"  - {item['lesson_type']}: {item['count']} events")

def show_events_with_meeting_details():
    """
    Show events that have meeting details.
    """
    print("\n🔍 Events with meeting details:")
    events_with_meetings = ClassEvent.objects.filter(
        meeting_link__isnull=False,
        meeting_link__gt=''
    ).select_related('class_instance')
    
    for event in events_with_meetings:
        print(f"  - {event.title}")
        print(f"    Class: {event.class_instance.name}")
        print(f"    Meeting Link: {event.meeting_link}")
        print(f"    Current lesson_type: {event.lesson_type}")
        print()

if __name__ == "__main__":
    print("🚀 ClassEvent Lesson Type Update Script")
    print("=" * 50)
    
    # Show current state
    show_current_lesson_types()
    show_events_with_meeting_details()
    
    # Run the update
    update_lesson_types()
    
    print("\n🎉 Script completed!")
