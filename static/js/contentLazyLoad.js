
// Check for IntersectionObserver support
if ('IntersectionObserver' in window) {
  document.addEventListener("DOMContentLoaded", function() {

    function handleIntersection(entries) {
      entries.map((entry) => {
        if (entry.isIntersecting) {
          entry.target.style.backgroundImage = "url('"+entry.target.dataset.bgimage+"')";
          observer.unobserve(entry.target);
        }
      });
    }

    const headers = document.querySelectorAll('.lazyLoadClass');
    const observer = new IntersectionObserver(
      handleIntersection
    );
    headers.forEach(header => observer.observe(header));
  });
} else {
  // No interaction support? Load all background images automatically
  const headers = document.querySelectorAll('.lazyLoadClass');
  headers.forEach(header => {
    header.style.backgroundImage = "url('"+header.dataset.bgimage+"')";
  });
}