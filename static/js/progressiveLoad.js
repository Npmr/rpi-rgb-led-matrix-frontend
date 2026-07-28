document.addEventListener('DOMContentLoaded', function() {
    var lazyImages = document.querySelectorAll('.lazy-image');
    var lazyVideos = document.querySelectorAll('.lazy-video');
    
    function supportsFormat(format) {
        var canvas = document.createElement('canvas');
        if (format === 'avif') {
            return canvas.toDataURL('image/avif').indexOf('data:image/avif') === 0;
        }
        if (format === 'webp') {
            return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
        }
        return true;
    }
    
    var supportsAVIF = supportsFormat('avif');
    var supportsWebP = supportsFormat('webp');
    
    function loadImage(img) {
        var fullAvif = img.dataset.fullAvif;
        var fullWebp = img.dataset.fullWebp;
        var fullOriginal = img.dataset.fullOriginal;
        var srcset = img.dataset.srcset;
        var sizes = img.dataset.sizes;
        
        if (srcset && sizes) {
            img.srcset = srcset;
            img.sizes = sizes;
        }
        
        if (supportsAVIF && fullAvif) {
            img.srcset = fullAvif + ' 600w';
        } else if (supportsWebP && fullWebp) {
            img.srcset = fullWebp + ' 600w';
        } else if (fullOriginal) {
            img.srcset = fullOriginal + ' 600w';
        }
        
        img.onload = function() {
            img.classList.add('loaded');
            img.style.filter = 'blur(0px)';
        };
        
        if (img.complete) {
            img.onload();
        }
    }
    
    function handleVideo(video) {
        video.load();
        video.classList.add('loaded');
    }
    
    function preloadFullImage(img) {
        var fullAvif = img.dataset.fullAvif;
        var fullWebp = img.dataset.fullWebp;
        var fullOriginal = img.dataset.fullOriginal;
        
        var link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        
        if (supportsAVIF && fullAvif) {
            link.href = fullAvif;
            link.type = 'image/avif';
        } else if (supportsWebP && fullWebp) {
            link.href = fullWebp;
            link.type = 'image/webp';
        } else if (fullOriginal) {
            link.href = fullOriginal;
        }
        
        document.head.appendChild(link);
    }
    
    if ('IntersectionObserver' in window) {
        var imageObserver = new IntersectionObserver(function(entries, observer) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    var target = entry.target;
                    if (target.tagName === 'IMG') {
                        loadImage(target);
                        if (target.dataset.fullAvif || target.dataset.fullWebp || target.dataset.fullOriginal) {
                            setTimeout(function() { preloadFullImage(target); }, 1000);
                        }
                    } else if (target.tagName === 'VIDEO') {
                        handleVideo(target);
                    }
                    observer.unobserve(target);
                }
            });
        }, {
            rootMargin: '200px 0px',
            threshold: 0.01
        });
        
        lazyImages.forEach(function(img) { imageObserver.observe(img); });
        lazyVideos.forEach(function(video) { imageObserver.observe(video); });
    } else {
        lazyImages.forEach(loadImage);
        lazyVideos.forEach(handleVideo);
    }
    
    document.addEventListener('click', function(e) {
        var img = e.target.closest('.lazy-image');
        if (img && !img.classList.contains('loaded')) {
            loadImage(img);
        }
    }, true);
});

function filterFunction() {
    var activePanel = document.querySelector('.tabs__panel--active');
    if (!activePanel) return;
    
    var checkboxes = activePanel.querySelectorAll('.filter-bar input[type="checkbox"]');
    var grid = activePanel.querySelector('.media-grid');
    if (!grid) return;
    
    var cards = grid.querySelectorAll('.media-card');
    
    cards.forEach(function(card) {
        var orientation = card.dataset.orientation;
        var show = false;
        
        checkboxes.forEach(function(cb) {
            var label = cb.closest('label');
            if (!label) return;
            var text = label.textContent.trim().toLowerCase();
            if (cb.checked && text === orientation) {
                show = true;
            }
        });
        
        card.style.display = show ? '' : 'none';
    });
}
