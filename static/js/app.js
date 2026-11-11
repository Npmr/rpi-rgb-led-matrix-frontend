/* ============================================================
   App JS - Interactive Components
   Sidebar toggle, tab switching, form helpers
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    // --- Sidebar Toggle (Mobile) ---
    var menuBtn = document.getElementById('mobile-menu-btn');
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    if (menuBtn && sidebar && overlay) {
        menuBtn.addEventListener('click', function () {
            sidebar.classList.toggle('layout__sidebar--open');
            overlay.classList.toggle('sidebar-overlay--active');
        });
        overlay.addEventListener('click', function () {
            sidebar.classList.remove('layout__sidebar--open');
            overlay.classList.remove('sidebar-overlay--active');
        });
        // Close sidebar on nav link click (mobile)
        sidebar.querySelectorAll('.nav__link').forEach(function (link) {
            link.addEventListener('click', function () {
                if (window.innerWidth <= 768) {
                    sidebar.classList.remove('layout__sidebar--open');
                    overlay.classList.remove('sidebar-overlay--active');
                }
            });
        });
    }

    // --- Tab Switching ---
    var tabContainers = document.querySelectorAll('.tabs');
    tabContainers.forEach(function (container) {
        var tabs = container.querySelectorAll('.tabs__tab');
        var panelContainer = container.nextElementSibling;
        if (!panelContainer) return;
        var panels = panelContainer.querySelectorAll('.tabs__panel');

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function (e) {
                e.preventDefault();
                var targetId = tab.getAttribute('data-tab') || tab.getAttribute('href');
                if (!targetId) return;

                // Deactivate all
                tabs.forEach(function (t) { t.classList.remove('tabs__tab--active'); });
                panels.forEach(function (p) { p.classList.remove('tabs__panel--active'); });

                // Activate clicked
                tab.classList.add('tabs__tab--active');
                var targetPanel = panelContainer.querySelector(targetId);
                if (targetPanel) {
                    targetPanel.classList.add('tabs__panel--active');
                }
            });
        });
    });

    // --- Auto-dismiss flash messages ---
    var flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function (msg) {
        var dismiss = msg.querySelector('.flash-dismiss');
        if (dismiss) {
            dismiss.addEventListener('click', function () {
                msg.style.transition = 'opacity 0.3s, transform 0.3s';
                msg.style.opacity = '0';
                msg.style.transform = 'translateY(-10px)';
                setTimeout(function () { msg.remove(); }, 300);
            });
        }
        // Auto-dismiss after 5 seconds
        setTimeout(function () {
            if (msg.parentElement) {
                msg.style.transition = 'opacity 0.3s, transform 0.3s';
                msg.style.opacity = '0';
                msg.style.transform = 'translateY(-10px)';
                setTimeout(function () { msg.remove(); }, 300);
            }
        }, 5000);
    });

    // --- Confirm dangerous actions ---
    var dangerForms = document.querySelectorAll('form[data-confirm]');
    dangerForms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            var message = form.getAttribute('data-confirm') || 'Are you sure?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // Buttons that target another endpoint via formaction cannot live in their
    // own <form> (nested forms are dropped by the parser), so confirm on click.
    var dangerButtons = document.querySelectorAll('button[data-confirm]');
    dangerButtons.forEach(function (button) {
        button.addEventListener('click', function (e) {
            var message = button.getAttribute('data-confirm') || 'Are you sure?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

});
