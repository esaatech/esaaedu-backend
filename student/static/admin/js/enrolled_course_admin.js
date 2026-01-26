/**
 * EnrolledCourse Admin JavaScript
 * Filters classes based on selected course
 * Note: For dynamic filtering, the form will reload when course changes
 */
(function() {
    'use strict';
    
    function initEnrolledCourseAdmin() {
        // Check if django.jQuery is available
        if (typeof django === 'undefined' || typeof django.jQuery === 'undefined') {
            // Retry after a short delay
            setTimeout(initEnrolledCourseAdmin, 50);
            return;
        }
        
        var $ = django.jQuery;
        
        $(document).ready(function() {
            const courseField = $('#id_course');
            const classField = $('#id_class_instance');
            
            // Exit if fields not found (might be on a different page)
            if (!courseField.length || !classField.length) {
                return;
            }
            
            // Add helper text to class field
            if (!classField.next('.help').length) {
                classField.after('<p class="help">Select a course first to see available classes</p>');
            }
            
            // Function to show/hide class field based on course selection
            function updateClassFieldVisibility() {
                const courseId = courseField.val();
                
                if (!courseId) {
                    // No course selected - disable and clear class field
                    classField.prop('disabled', true);
                    classField.closest('.form-row').find('.help').text('Select a course first to see available classes');
                } else {
                    // Course selected - enable class field
                    classField.prop('disabled', false);
                    classField.closest('.form-row').find('.help').text('Select a class for this enrollment (optional)');
                    
                    // Note: The actual filtering is handled by Django form's queryset
                    // which is updated when the form is reloaded
                }
            }
            
            // Watch for course changes
            courseField.on('change', function() {
                updateClassFieldVisibility();
                // Note: For full dynamic filtering without page reload, we'd need an API endpoint
                // For now, the form's __init__ method handles filtering when the form loads
            });
            
            // Initial update
            updateClassFieldVisibility();
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEnrolledCourseAdmin);
    } else {
        initEnrolledCourseAdmin();
    }
})();

