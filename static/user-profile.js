// User profile modal functionality
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const userIcon = document.getElementById('user-icon');
    const modal = document.getElementById('user-profile-modal');
    const closeBtn = modal.querySelector('.close');
    const saveBtn = document.getElementById('save-profile-btn');
    const closeProfileBtn = document.getElementById('close-profile-btn');
    
    // Open modal when clicking user icon
    userIcon.addEventListener('click', function() {
        loadUserProfile();
        modal.style.display = 'block';
    });
    
    // Close modal with X button
    closeBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });
    
    // Close modal with Close button
    closeProfileBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });
    
    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // Save profile
    saveBtn.addEventListener('click', saveUserProfile);
    
    // Load calendar context and user profile on page load
    loadCalendarContext();
    
    // Function to load user profile
    async function loadUserProfile() {
        try {
            const response = await fetch('/api/user_profile');
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Populate form
            document.getElementById('user-id').value = data.user_id;
            document.getElementById('user-name').value = data.user_name;
            document.getElementById('user-context').value = data.user_context;
            
        } catch (error) {
            console.error('Error loading user profile:', error);
            showNotification('Failed to load user profile', 'error');
        }
    }
    
    // Function to save user profile
    async function saveUserProfile() {
        try {
            const userId = document.getElementById('user-id').value;
            const userName = document.getElementById('user-name').value;
            const userContext = document.getElementById('user-context').value;
            
            if (!userName) {
                showNotification('Please enter a name', 'error');
                return;
            }
            
            const response = await fetch('/api/user_profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    user_name: userName,
                    user_context: userContext
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.status === 'success') {
                showNotification('Profile saved successfully', 'success');
                modal.style.display = 'none';
            } else {
                throw new Error(result.message || 'Failed to save profile');
            }
            
        } catch (error) {
            console.error('Error saving user profile:', error);
            showNotification(`Failed to save profile: ${error.message}`, 'error');
        }
    }
    
    // Function to load calendar context
    async function loadCalendarContext() {
        try {
            const response = await fetch('/api/calendar_context');
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Update calendar context text
            document.getElementById('calendar-context-text').textContent = data.context;
            
        } catch (error) {
            console.error('Error loading calendar context:', error);
            // Silently fail - this is not critical
        }
    }
    
    // Function to show notification
    function showNotification(message, type) {
        // Check if notification container exists
        let container = document.getElementById('notification-container');
        
        if (!container) {
            // Create container if it doesn't exist
            container = document.createElement('div');
            container.id = 'notification-container';
            document.body.appendChild(container);
        }
        
        // Create notification
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        // Add to container
        container.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => {
                container.removeChild(notification);
            }, 300);
        }, 3000);
    }
});