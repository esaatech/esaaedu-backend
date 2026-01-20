/**
 * Program Admin JavaScript
 * Enforces mutual exclusivity between category and courses fields
 * Shows warnings but allows users to change their selection
 */

(function() {
    'use strict';
    
    function initProgramAdmin() {
        // Check if django.jQuery is available
        if (typeof django === 'undefined' || typeof django.jQuery === 'undefined') {
            // Retry after a short delay
            setTimeout(initProgramAdmin, 50);
            return;
        }
        
        var $ = django.jQuery;
        
        $(document).ready(function() {
            const categoryField = $('#id_category');
            const coursesSelect = $('#id_courses_from'); // filter_horizontal uses this ID
            const coursesFieldset = coursesSelect.length ? coursesSelect.closest('fieldset') : null;
            const categoryFieldset = categoryField.closest('fieldset');
            
            // Exit if fields not found (might be on a different page)
            if (!categoryField.length) {
                return;
            }
            
            // Function to check if courses are selected
            function hasCoursesSelected() {
                // Check the "Chosen courses" select box (right side of filter_horizontal)
                const chosenCourses = $('#id_courses_to option');
                return chosenCourses && chosenCourses.length > 0;
            }
            
            // Function to show/hide warnings (but don't disable fields)
            function updateWarnings() {
                if (!categoryField.length || !coursesFieldset) {
                    return; // Fields not found, exit early
                }
                
                const categoryValue = categoryField.val();
                const hasCourses = hasCoursesSelected();
                
                // Remove all existing warnings first
                coursesFieldset.find('.category-warning').remove();
                categoryFieldset.find('.courses-warning').remove();
                
                if (categoryValue && hasCourses) {
                    // Both selected - show warning but don't disable
                    coursesFieldset.prepend(
                        '<div class="category-warning" style="background: #f8d7da; border: 1px solid #dc3545; padding: 10px; margin-bottom: 10px; border-radius: 4px; clear: both;">' +
                        '<strong>⚠️ Warning:</strong> You have selected both a category and specific courses. ' +
                        'Please choose only one. The other will be cleared when you save.' +
                        '</div>'
                    );
                    categoryFieldset.append(
                        '<div class="courses-warning" style="background: #f8d7da; border: 1px solid #dc3545; padding: 10px; margin-top: 10px; border-radius: 4px;">' +
                        '<strong>⚠️ Warning:</strong> You have selected both a category and specific courses. ' +
                        'Please choose only one. The other will be cleared when you save.' +
                        '</div>'
                    );
                } else if (categoryValue) {
                    // Only category selected - show info message
                    coursesFieldset.prepend(
                        '<div class="category-warning" style="background: #d1ecf1; border: 1px solid #bee5eb; padding: 10px; margin-bottom: 10px; border-radius: 4px; clear: both;">' +
                        '<strong>ℹ️ Info:</strong> Category selected. All courses in this category will be included. ' +
                        'You can still change your selection if needed.' +
                        '</div>'
                    );
                } else if (hasCourses) {
                    // Only courses selected - show info message
                    categoryFieldset.append(
                        '<div class="courses-warning" style="background: #d1ecf1; border: 1px solid #bee5eb; padding: 10px; margin-top: 10px; border-radius: 4px;">' +
                        '<strong>ℹ️ Info:</strong> Specific courses selected. Only these courses will be included. ' +
                        'You can still change your selection if needed.' +
                        '</div>'
                    );
                }
            }
            
            // Initial state check (with delay to ensure DOM is ready)
            setTimeout(updateWarnings, 100);
            
            // Watch for category changes
            categoryField.on('change', function() {
                updateWarnings();
            });
            
            // Watch for courses changes in filter_horizontal widget
            // This watches for clicks on the selector buttons
            $(document).on('click', function(e) {
                // Check if the click was on a selector button
                const target = $(e.target);
                if (target.closest('.selector-choose, .selector-remove, .selector-chooseall, .selector-removeall').length) {
                    setTimeout(updateWarnings, 200); // Delay to let the widget update
                }
            });
            
            // Also watch for changes in the select boxes themselves
            $(document).on('change', '#id_courses_from, #id_courses_to', function() {
                setTimeout(updateWarnings, 100);
            });
            
            // Before form submission, clear the other field if one is selected
            $('form').on('submit', function(e) {
                const categoryValue = categoryField.val();
                const hasCourses = hasCoursesSelected();
                
                if (categoryValue && hasCourses) {
                    // Both selected - clear courses (category takes priority)
                    e.preventDefault();
                    if (confirm('You have selected both a category and specific courses. The category will be used and courses will be cleared. Continue?')) {
                        // Clear courses by removing all
                        const removeAllLink = $('#id_courses_remove_all_link');
                        if (removeAllLink.length) {
                            removeAllLink[0].click();
                        }
                        // Submit again after clearing
                        setTimeout(function() {
                            $('form').off('submit').submit();
                        }, 100);
                    }
                } else if (categoryValue) {
                    // Category selected - ensure courses are cleared
                    const removeAllLink = $('#id_courses_remove_all_link');
                    if (removeAllLink.length && hasCoursesSelected()) {
                        removeAllLink[0].click();
                    }
                } else if (hasCourses) {
                    // Courses selected - ensure category is cleared
                    categoryField.val('');
                }
            });
        });
    }
    
    // Start initialization
    initProgramAdmin();
    
})();
