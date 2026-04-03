// Global AuthVote Scripts

document.addEventListener('DOMContentLoaded', () => {
    console.log("AuthVote platform initialized.");
    
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease-out';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // Form confirmation handles
    const deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            if (!confirm("Are you sure you want to perform this action?")) {
                e.preventDefault();
            }
        });
    });
});
