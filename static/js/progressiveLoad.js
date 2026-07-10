document.addEventListener('DOMContentLoaded', function() {
    const lazyImages = document.querySelectorAll('.lazy-image');
    const lazyVideos = document.querySelectorAll('.lazy-video');
    
    function supportsFormat(format) {
        const canvas = document.createElement('canvas');
        if (format === 'avif') {
            return canvas.toDataURL('image/avif').indexOf('data:image/avif') === 0;
        }
        if (format === 'webp') {
            return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
        }
        return true;
    }
    
    const supportsAVIF = supportsFormat('avif');
    const supportsWebP = supportsFormat('webp');
    
    function loadImage(img) {
        const fullAvif = img.dataset.fullAvif;
        const fullWebp = img.dataset.fullWebp;
        const fullOriginal = img.dataset.fullOriginal;
        const srcset = img.dataset.srcset;
        const sizes = img.dataset.sizes;
        
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
        const fullAvif = img.dataset.fullAvif;
        const fullWebp = img.dataset.fullWebp;
        const fullOriginal = img.dataset.fullOriginal;
        
        const link = document.createElement('link');
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
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const target = entry.target;
                    if (target.tagName === 'IMG') {
                        loadImage(target);
                        if (target.dataset.fullAvif || target.dataset.fullWebp || target.dataset.fullOriginal) {
                            setTimeout(() => preloadFullImage(target), 1000);
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
        
        lazyImages.forEach(img => imageObserver.observe(img));
        lazyVideos.forEach(video => imageObserver.observe(video));
    } else {
        lazyImages.forEach(loadImage);
        lazyVideos.forEach(handleVideo);
    }
    
    document.addEventListener('click', function(e) {
        const img = e.target.closest('.lazy-image');
        if (img && !img.classList.contains('loaded')) {
            loadImage(img);
        }
    }, true);
    
    const filterCheckboxes = document.querySelectorAll('.filter-fieldset input[type="checkbox"]');
    filterCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', filterFunction);
    });
});

function filterFunction() {
    const checkBoxVertical = document.getElementById("checkbox-vertical");
    const checkBoxHorizontal = document.getElementById("checkbox-horizontal");
    const checkBoxSquare = document.getElementById("checkbox-square");
    
    const grids = document.querySelectorAll('.media-grid');
    
    grids.forEach(grid => {
        const cards = grid.querySelectorAll('.media-card');
        
        cards.forEach(card => {
            const orientation = card.dataset.orientation;
            let show = false;
            
            if (orientation === 'vertical' && checkBoxVertical.checked) show = true;
            if (orientation === 'horizontal' && checkBoxHorizontal.checked) show = true;
            if (orientation === 'square' && checkBoxSquare.checked) show = true;
            
            card.style.display = show ? 'block' : 'none';
        });
    });
}