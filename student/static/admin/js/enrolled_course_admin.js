/**
 * EnrolledCourse Admin JavaScript
 * Adds "Load Classes" and "Load Lessons" buttons with AJAX loading
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
            const lessonField = $('#id_current_lesson');
            
            // Exit if fields not found (might be on a different page)
            if (!courseField.length) {
                return;
            }
            
            // Get CSRF token for AJAX requests
            function getCookie(name) {
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }
                    }
                }
                return cookieValue;
            }
            const csrftoken = getCookie('csrftoken');
            
            // Create Load Classes button
            let loadClassesBtn = null;
            if (classField.length) {
                const classRow = classField.closest('.form-row');
                if (!classRow.find('.load-classes-btn').length) {
                    loadClassesBtn = $('<button>')
                        .attr('type', 'button')
                        .addClass('load-classes-btn')
                        .text('Load Classes')
                        .css({
                            'margin-left': '10px',
                            'padding': '5px 10px',
                            'cursor': 'pointer'
                        });
                    classField.after(loadClassesBtn);
                } else {
                    loadClassesBtn = classRow.find('.load-classes-btn');
                }
            }
            
            // Create Load Lessons button
            let loadLessonsBtn = null;
            if (lessonField.length) {
                const lessonRow = lessonField.closest('.form-row');
                if (!lessonRow.find('.load-lessons-btn').length) {
                    loadLessonsBtn = $('<button>')
                        .attr('type', 'button')
                        .addClass('load-lessons-btn')
                        .text('Load Lessons')
                        .css({
                            'margin-left': '10px',
                            'padding': '5px 10px',
                            'cursor': 'pointer'
                        });
                    lessonField.after(loadLessonsBtn);
                } else {
                    loadLessonsBtn = lessonRow.find('.load-lessons-btn');
                }
            }
            
            // Create spinner element
            function createSpinner() {
                return $('<span>')
                    .addClass('loading-spinner')
                    .html('&#8635;')
                    .css({
                        'display': 'inline-block',
                        'margin-left': '5px',
                        'animation': 'spin 1s linear infinite',
                        'font-size': '14px'
                    });
            }
            
            // Add CSS for spinner animation
            if (!$('#enrolled-course-spinner-style').length) {
                $('<style>')
                    .attr('id', 'enrolled-course-spinner-style')
                    .text('@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }')
                    .appendTo('head');
            }
            
            // Function to update button states based on course selection
            function updateButtonStates() {
                const courseId = courseField.val();
                const hasCourse = !!courseId;
                
                if (loadClassesBtn) {
                    loadClassesBtn.prop('disabled', !hasCourse);
                    if (!hasCourse) {
                        loadClassesBtn.css('opacity', '0.5');
                    } else {
                        loadClassesBtn.css('opacity', '1');
                    }
                }
                
                if (loadLessonsBtn) {
                    loadLessonsBtn.prop('disabled', !hasCourse);
                    if (!hasCourse) {
                        loadLessonsBtn.css('opacity', '0.5');
                    } else {
                        loadLessonsBtn.css('opacity', '1');
                    }
                }
                
                if (classField.length) {
                    if (!hasCourse) {
                        classField.prop('disabled', true);
                        classField.val('');
                    }
                }
                
                if (lessonField.length) {
                    if (!hasCourse) {
                        lessonField.prop('disabled', true);
                        lessonField.val('');
                    }
                }
            }
            
            // Load classes via AJAX
            function loadClasses() {
                const courseId = courseField.val();
                if (!courseId) {
                    alert('Please select a course first');
                    return;
                }
                
                // Disable button and show spinner
                loadClassesBtn.prop('disabled', true);
                const spinner = createSpinner();
                loadClassesBtn.after(spinner);
                
                // Make AJAX request
                $.ajax({
                    url: `/api/student/admin/courses/${courseId}/classes/`,
                    method: 'GET',
                    xhrFields: {
                        withCredentials: true
                    },
                    headers: {
                        'X-CSRFToken': csrftoken
                    },
                    success: function(data) {
                        // Clear existing options
                        classField.empty();
                        classField.append($('<option>').val('').text('---------'));
                        
                        // Add classes
                        if (data.length === 0) {
                            classField.append($('<option>').val('').text('No classes available'));
                            alert('No active classes found for this course');
                        } else {
                            data.forEach(function(cls) {
                                const option = $('<option>')
                                    .val(cls.id)
                                    .text(cls.name + (cls.available_spots >= 0 ? ` (${cls.available_spots} spots available)` : ''));
                                classField.append(option);
                            });
                            classField.prop('disabled', false);
                        }
                    },
                    error: function(xhr) {
                        let errorMsg = 'Failed to load classes';
                        if (xhr.responseJSON && xhr.responseJSON.error) {
                            errorMsg = xhr.responseJSON.error;
                        }
                        alert(errorMsg);
                        classField.prop('disabled', true);
                    },
                    complete: function() {
                        // Remove spinner and re-enable button
                        spinner.remove();
                        loadClassesBtn.prop('disabled', false);
                        updateButtonStates();
                    }
                });
            }
            
            // Load lessons via AJAX
            function loadLessons() {
                const courseId = courseField.val();
                if (!courseId) {
                    alert('Please select a course first');
                    return;
                }
                
                // Disable button and show spinner
                loadLessonsBtn.prop('disabled', true);
                const spinner = createSpinner();
                loadLessonsBtn.after(spinner);
                
                // Make AJAX request
                $.ajax({
                    url: `/api/student/admin/courses/${courseId}/lessons/`,
                    method: 'GET',
                    xhrFields: {
                        withCredentials: true
                    },
                    headers: {
                        'X-CSRFToken': csrftoken
                    },
                    success: function(data) {
                        // Clear existing options
                        lessonField.empty();
                        lessonField.append($('<option>').val('').text('---------'));
                        
                        // Add lessons
                        if (data.length === 0) {
                            lessonField.append($('<option>').val('').text('No lessons available'));
                            alert('No lessons found for this course');
                        } else {
                            data.forEach(function(lesson) {
                                const option = $('<option>')
                                    .val(lesson.id)
                                    .text(`Lesson ${lesson.order}: ${lesson.title}`);
                                lessonField.append(option);
                            });
                            lessonField.prop('disabled', false);
                        }
                    },
                    error: function(xhr) {
                        let errorMsg = 'Failed to load lessons';
                        if (xhr.responseJSON && xhr.responseJSON.error) {
                            errorMsg = xhr.responseJSON.error;
                        }
                        alert(errorMsg);
                        lessonField.prop('disabled', true);
                    },
                    complete: function() {
                        // Remove spinner and re-enable button
                        spinner.remove();
                        loadLessonsBtn.prop('disabled', false);
                        updateButtonStates();
                    }
                });
            }
            
            // Attach click handlers
            if (loadClassesBtn) {
                loadClassesBtn.on('click', loadClasses);
            }
            
            if (loadLessonsBtn) {
                loadLessonsBtn.on('click', loadLessons);
            }
            
            // Watch for course changes
            courseField.on('change', function() {
                updateButtonStates();
                // Clear class and lesson fields when course changes
                if (classField.length) {
                    classField.val('');
                    classField.empty();
                    classField.append($('<option>').val('').text('---------'));
                }
                if (lessonField.length) {
                    lessonField.val('');
                    lessonField.empty();
                    lessonField.append($('<option>').val('').text('---------'));
                }
            });
            
            // Initial update
            updateButtonStates();
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEnrolledCourseAdmin);
    } else {
        initEnrolledCourseAdmin();
    }
})();
