// Инициализация карусели Bootstrap (если требуется управление через JS)
document.addEventListener('DOMContentLoaded', function () {
    var carouselElement = document.querySelector('#mainCarousel');
    if (carouselElement && window.bootstrap) {
        new bootstrap.Carousel(carouselElement, { interval: 5000, ride: 'carousel' });
    }
});

