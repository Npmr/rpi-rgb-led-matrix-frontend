/* ============================================================
   App JS - Interactive Components
   Tab switching, mobile menu, form helpers
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    // --- Tab Switching ---
    const tabContainers = document.querySelectorAll('.tabs');
    tabContainers.forEach(function (container) {
        const tabs = container.querySelectorAll('.tabs__tab');
        const panelContainer = container.nextElementSibling;
        if (!panelContainer) return;
        const panels = panelContainer.querySelectorAll('.tabs__panel');

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function (e) {
                e.preventDefault();
                const targetId = tab.getAttribute('data-tab') || tab.getAttribute('href');
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

    // --- Mobile Menu Toggle ---
    var menuBtn = document.querySelector('.mobile-menu-btn');
    var nav = document.querySelector('.nav');
    if (menuBtn && nav) {
        menuBtn.addEventListener('click', function () {
            nav.classList.toggle('nav--open');
        });
        // Close on link click
        nav.querySelectorAll('.nav__link').forEach(function (link) {
            link.addEventListener('click', function () {
                nav.classList.remove('nav--open');
            });
        });
    }

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

});
