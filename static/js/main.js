// Firmowy Kiosk - Główny plik JavaScript

// Stan aplikacji
let currentSection = 'wykresy';
let rotationTimer = 30;
let rotationInterval = null;
let timerInterval = null;
let charts = {};
let slides = [];
let currentSlide = 0;
let slideInterval = null;
let isRotationPaused = false;
let pagesVisible = {};
let availableSections = ['wykresy', 'inspiracje', 'zdjecia', 'o-nas', 'powerbi'];

// ==================== INICJALIZACJA ====================

document.addEventListener('DOMContentLoaded', () => {
    // Inicjalizuj aplikację
    initializeApp();
    
    // Sprawdź zapisany tryb ciemny
    if (localStorage.getItem('darkMode') === 'true') {
        document.documentElement.classList.add('dark');
        updateThemeButton(true);
    }
    
    // Ukryj kursor w trybie kiosk po 5 sekundach bezczynności
    let cursorTimeout;
    document.addEventListener('mousemove', () => {
        document.body.classList.remove('kiosk-mode');
        clearTimeout(cursorTimeout);
        cursorTimeout = setTimeout(() => {
            document.body.classList.add('kiosk-mode');
        }, 5000);
    });
});

// ==================== FUNKCJE GŁÓWNE ====================

async function initializeApp() {
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    await loadContent();
    await loadMachines();
    await loadInspirationsData();
    await loadSlidesData();
    
    startAutoRotation();
    
    if (availableSections.length > 0) {
        showSection(availableSections[0]);
    } else {
        showSection('wykresy');
    }
    
    setInterval(refreshContent, 5 * 60 * 1000);
}

function updateCurrentTime() {
    const now = new Date();
    const timeStr = now.toLocaleString('pl-PL', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const el = document.getElementById('current-time');
    if (el) el.textContent = timeStr;
}

// ==================== NAWIGACJA SEKCJI ====================

function showSection(sectionName) {
    if (pagesVisible && pagesVisible[sectionName] === false && sectionName !== 'dashboard') {
        console.warn('Sekcja ukryta:', sectionName);
        return;
    }

    console.log('Changing section to:', sectionName);
    
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active', 'fade-in');
        section.style.display = 'none';
    });
    
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-orange-100', 'text-orange-600', 'dark:bg-gray-700', 'dark:text-orange-400');
    });
    
    const section = document.getElementById(`section-${sectionName}`);
    if (section) {
        section.style.display = 'block';
        setTimeout(() => {
            section.classList.add('active');
        }, 10);
    }
    
    const btn = document.querySelector(`[data-section="${sectionName}"]`);
    if (btn) {
        btn.classList.add('active', 'bg-orange-100', 'text-orange-600', 'dark:bg-gray-700', 'dark:text-orange-400');
    }
    
    currentSection = sectionName;
    
    if (sectionName === 'zdjecia') {
        startSlideshow();
    } else {
        stopSlideshow();
    }
    
    resetRotationTimer();
}

// ==================== AUTOMATYCZNA ROTACJA ====================

function rotateSection() {
    if (availableSections.length <= 1) return;
    let currentIndex = availableSections.indexOf(currentSection);
    let nextIndex = (currentIndex + 1) % availableSections.length;
    showSection(availableSections[nextIndex]);
}

function startAutoRotation() {
    if (rotationInterval) clearInterval(rotationInterval);
    if (timerInterval) clearInterval(timerInterval);

    rotationInterval = setInterval(() => {
        if (isRotationPaused) return;
        rotateSection();
    }, 30000);
    
    rotationTimer = 30;
    timerInterval = setInterval(() => {
        if (isRotationPaused) return;
        rotationTimer--;
        if (rotationTimer < 0) rotationTimer = 29;
        const timerElement = document.getElementById('rotation-timer');
        if (timerElement) timerElement.textContent = rotationTimer;
    }, 1000);
}

function resetRotationTimer() {
    rotationTimer = 30;
    const el = document.getElementById('rotation-timer');
    if (el) el.textContent = rotationTimer;
}

function stopAutoRotation() {
    if (rotationInterval) { clearInterval(rotationInterval); rotationInterval = null; }
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

function toggleAutoRotation() {
    const btn = document.getElementById('rotation-toggle');
    const indicator = document.getElementById('rotation-indicator');
    
    if (isRotationPaused) {
        isRotationPaused = false;
        startAutoRotation();
        if (btn) {
            btn.textContent = 'Stop';
            btn.classList.remove('bg-green-500', 'hover:bg-green-600');
            btn.classList.add('bg-red-500', 'hover:bg-red-600');
        }
        if (indicator) {
            indicator.classList.add('animate-pulse', 'bg-green-500');
            indicator.classList.remove('bg-gray-400');
        }
    } else {
        isRotationPaused = true;
        stopAutoRotation();
        if (btn) {
            btn.textContent = 'Start';
            btn.classList.remove('bg-red-500', 'hover:bg-red-600');
            btn.classList.add('bg-green-500', 'hover:bg-green-600');
        }
        if (indicator) {
            indicator.classList.remove('animate-pulse', 'bg-green-500');
            indicator.classList.add('bg-gray-400');
        }
    }
}

// ==================== WYKRESY ====================

let currentMachineCode = '1310';
let currentStartDay = 1;

async function loadMachines() {
    try {
        const response = await fetch('/api/machines');
        const machines = await response.json();
        const select = document.getElementById('machine-select');
        const slider = document.getElementById('day-slider');
        
        if (select && machines.length > 0) {
            select.innerHTML = '';
            machines.forEach(machine => {
                const option = document.createElement('option');
                option.value = machine.kod;
                option.textContent = machine.label;
                select.appendChild(option);
            });
            currentMachineCode = machines[0].kod;
            loadChartData(currentMachineCode, currentStartDay);
            select.addEventListener('change', function() {
                currentMachineCode = this.value;
                loadChartData(currentMachineCode, currentStartDay);
            });
        }
        
        if (slider) {
            slider.addEventListener('input', function() {
                currentStartDay = parseInt(this.value);
                updateDayRangeLabel(currentStartDay);
                loadChartData(currentMachineCode, currentStartDay);
            });
        }
    } catch (error) {
        console.error('Błąd ładowania listy maszyn:', error);
    }
}

function updateDayRangeLabel(startDay) {
    const label = document.getElementById('day-range-label');
    if (label) {
        const endDay = startDay + 6;
        label.textContent = `Dni ${startDay}-${endDay}`;
    }
}

async function loadChartData(kod = '1310', startDay = 1) {
    try {
        const response = await fetch(`/api/chart-data?kod=${encodeURIComponent(kod)}&start_day=${startDay}`);
        const data = await response.json();
        if (data && data.series && data.series.length > 0) {
            createCharts(data);
        }
    } catch (error) {
        console.error('Błąd ładowania danych wykresów:', error);
    }
}

function createCombinedChart(series) {
    const ctxProduction = document.getElementById('productionChart');
    if (!ctxProduction) return;
    if (charts.production) charts.production.destroy();
    
    const allDays = new Set();
    series.forEach(s => s.x.forEach(day => allDays.add(day)));
    const labels = Array.from(allDays).sort((a, b) => a - b).map(d => `Dzień ${d}`);
    const datasets = [];
    
    series.filter(s => s.type === 'bar').forEach(s => {
        const dataMap = {};
        s.x.forEach((day, i) => dataMap[day] = s.y[i]);
        datasets.push({
            type: 'bar',
            label: s.name,
            data: Array.from(allDays).sort((a, b) => a - b).map(day => dataMap[day] || 0),
            backgroundColor: s.color + 'CC',
            borderColor: s.color,
            borderWidth: 1,
            yAxisID: 'y'
        });
    });
    
    series.filter(s => s.type === 'line').forEach(s => {
        const dataMap = {};
        s.x.forEach((day, i) => dataMap[day] = s.y[i]);
        datasets.push({
            type: 'line',
            label: s.name,
            data: Array.from(allDays).sort((a, b) => a - b).map(day => dataMap[day] || null),
            borderColor: s.color,
            backgroundColor: s.color + '33',
            borderWidth: 2,
            tension: 0.1,
            yAxisID: 'y2'
        });
    });
    
    let maxValue = 0;
    series.forEach(s => {
        const seriesMax = Math.max(...s.y);
        if (seriesMax > maxValue) maxValue = seriesMax;
    });
    maxValue = Math.ceil(maxValue * 1.1);
    
    const isDark = document.documentElement.classList.contains('dark');
    const textColor = isDark ? '#FFFFFF' : '#1F2937';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    
    charts.production = new Chart(ctxProduction, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: true, position: 'bottom', labels: { color: textColor } }
            },
            scales: {
                y: {
                    type: 'linear', display: true, position: 'left', beginAtZero: true, max: maxValue,
                    ticks: { color: textColor }, grid: { color: gridColor },
                    title: { display: true, text: 'Produkcja dzienna', color: textColor }
                },
                y2: {
                    type: 'linear', display: true, position: 'right', beginAtZero: true, max: maxValue,
                    ticks: { color: textColor }, grid: { drawOnChartArea: false },
                    title: { display: true, text: 'Produkcja narastająca', color: textColor }
                },
                x: { ticks: { color: textColor }, grid: { display: false } }
            }
        }
    });
}

function createCharts(data) {
    if (data.series && Array.isArray(data.series)) {
        createCombinedChart(data.series);
    }
    
    const innovationData = [5, 7, 6, 8, 10, 9, 11];
    const efficiencyData = [85, 88, 90, 87, 92, 89, 94];
    const isDark = document.documentElement.classList.contains('dark');
    const textColor = isDark ? '#FFFFFF' : '#1F2937';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    
    const commonOptions = {
        responsive: true, maintainAspectRatio: true,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, ticks: { color: textColor }, grid: { color: gridColor } },
            x: { ticks: { color: textColor }, grid: { display: false } }
        }
    };
    
    const labels = ['Dzień 1', 'Dzień 2', 'Dzień 3', 'Dzień 4', 'Dzień 5', 'Dzień 6', 'Dzień 7'];
    
    const ctxInnovation = document.getElementById('innovationChart');
    if (ctxInnovation) {
        if (charts.innovation) charts.innovation.destroy();
        charts.innovation = new Chart(ctxInnovation, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Innowacje', data: innovationData,
                    backgroundColor: 'rgba(0, 78, 137, 0.2)', borderColor: 'rgba(0, 78, 137, 1)',
                    borderWidth: 3, tension: 0.4, fill: true
                }]
            },
            options: commonOptions
        });
    }
    
    const ctxEfficiency = document.getElementById('efficiencyChart');
    if (ctxEfficiency) {
        if (charts.efficiency) charts.efficiency.destroy();
        charts.efficiency = new Chart(ctxEfficiency, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Efektywność (%)', data: efficiencyData,
                    backgroundColor: 'rgba(40, 167, 69, 0.2)', borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 3, tension: 0.4, fill: true
                }]
            },
            options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, min: 0, max: 100 } } }
        });
    }
}

// ==================== INSPIRACJE ====================

async function loadInspirationsData() {
    try {
        const response = await fetch('/api/inspirations');
        const inspirations = await response.json();
        displayInspirations(inspirations);
    } catch (error) {
        console.error('Błąd ładowania inspiracji:', error);
    }
}

function displayInspirations(inspirations) {
    const container = document.getElementById('inspirations-container');
    if (!container) return;
    container.innerHTML = '';
    inspirations.forEach((insp, index) => {
        const card = document.createElement('div');
        card.className = 'inspiration-card bg-white dark:bg-gray-800 rounded-2xl shadow-xl overflow-hidden fade-in';
        card.style.animationDelay = `${index * 0.1}s`;
        card.innerHTML = `
            <img src="${insp.image_url}" alt="${insp.title}" class="w-full h-64 object-cover">
            <div class="p-6">
                <h3 class="text-2xl font-bold text-gray-800 dark:text-white mb-3">${insp.title}</h3>
                <p class="text-gray-600 dark:text-gray-300 text-lg leading-relaxed">${insp.description}</p>
            </div>
        `;
        container.appendChild(card);
    });
}

// ==================== POKAZ SLAJDÓW ====================

async function loadSlidesData() {
    try {
        const response = await fetch('/api/slides');
        slides = await response.json();
        if (slides.length === 0) {
            slides = [
                { url: '/static/images/slides/slide1.jpg', name: 'Slajd 1' },
                { url: '/static/images/slides/slide2.jpg', name: 'Slajd 2' },
                { url: '/static/images/slides/slide3.jpg', name: 'Slajd 3' }
            ];
        }
        createSlideshowDots();
    } catch (error) {
        console.error('Błąd ładowania slajdów:', error);
    }
}

function createSlideshowDots() {
    const dotsContainer = document.getElementById('slideshow-dots');
    if (!dotsContainer) return;
    dotsContainer.innerHTML = '';
    slides.forEach((_, index) => {
        const dot = document.createElement('div');
        dot.className = 'slide-dot';
        if (index === 0) dot.classList.add('active');
        dot.addEventListener('click', () => goToSlide(index));
        dotsContainer.appendChild(dot);
    });
}

function startSlideshow() {
    if (slides.length === 0) return;
    currentSlide = 0;
    showSlide(currentSlide);
    slideInterval = setInterval(() => {
        currentSlide = (currentSlide + 1) % slides.length;
        showSlide(currentSlide);
    }, 5000);
}

function stopSlideshow() {
    if (slideInterval) { clearInterval(slideInterval); slideInterval = null; }
}

function showSlide(index) {
    const img = document.getElementById('slideshow-image');
    if (!img || !slides[index]) return;
    img.style.opacity = '0';
    setTimeout(() => {
        img.src = slides[index].url;
        img.style.opacity = '1';
        document.querySelectorAll('.slide-dot').forEach((dot, i) => {
            dot.classList.toggle('active', i === index);
        });
    }, 400);
}

function goToSlide(index) {
    stopSlideshow();
    currentSlide = index;
    showSlide(currentSlide);
    startSlideshow();
}

// ==================== TRYB CIEMNY ====================

function toggleDarkMode() {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('darkMode', isDark);
    updateThemeButton(isDark);
    try { updateChartsTheme(isDark); } catch (e) {}
}

function updateThemeButton(isDark) {
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');
    if (themeIcon) themeIcon.textContent = isDark ? '☀️' : '🌙';
    if (themeText) themeText.textContent = isDark ? 'Tryb jasny' : 'Tryb ciemny';
}

function updateChartsTheme(isDark) {
    const textColor = isDark ? '#FFFFFF' : '#1F2937';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    Object.values(charts).forEach(chart => {
        if (chart && chart.options) {
            try {
                if (chart.options.plugins?.legend?.labels) chart.options.plugins.legend.labels.color = textColor;
                if (chart.options.scales) {
                    if (chart.options.scales.x?.ticks) chart.options.scales.x.ticks.color = textColor;
                    if (chart.options.scales.y) {
                        if (chart.options.scales.y.ticks) chart.options.scales.y.ticks.color = textColor;
                        if (chart.options.scales.y.grid) chart.options.scales.y.grid.color = gridColor;
                        if (chart.options.scales.y.title) chart.options.scales.y.title.color = textColor;
                    }
                    if (chart.options.scales.y2) {
                        if (chart.options.scales.y2.ticks) chart.options.scales.y2.ticks.color = textColor;
                        if (chart.options.scales.y2.title) chart.options.scales.y2.title.color = textColor;
                    }
                }
                chart.update();
            } catch (e) {}
        }
    });
}

// ==================== AUTO-REFRESH ====================

async function loadContent() {
    try {
        const response = await fetch('/api/content');
        const content = await response.json();
        
        if (content.settings) {
            const aboutEl = document.getElementById('about-text');
            if (aboutEl) aboutEl.textContent = content.settings.about_text;
            const headerEl = document.getElementById('header-title');
            if (headerEl) headerEl.textContent = content.settings.header_title;
            const footerEl = document.getElementById('footer-note');
            if (footerEl) footerEl.textContent = content.settings.footer_note;
        }

        if (content.visibility) {
            pagesVisible = content.visibility;
            const allPossible = ['wykresy', 'inspiracje', 'zdjecia', 'o-nas', 'powerbi', 'quiz'];
            availableSections = allPossible.filter(s => pagesVisible[s] !== false);
            
            allPossible.forEach(s => {
                const btn = document.querySelector(`.nav-btn[data-section="${s}"]`);
                const quizBtn = document.getElementById('nav-quiz');
                if (s === 'quiz' && quizBtn) {
                    quizBtn.style.display = pagesVisible['quiz'] === false ? 'none' : 'block';
                } else if (btn) {
                    btn.style.display = pagesVisible[s] === false ? 'none' : 'block';
                }
            });

            if (pagesVisible[currentSection] === false && availableSections.length > 0) {
                showSection(availableSections[0]);
            }
        }
        console.log("🔄 Treść załadowana.", pagesVisible);
    } catch (error) {
        console.error('Błąd ładowania treści:', error);
    }
}

async function refreshContent() {
    console.log('🔄 Automatyczne odświeżanie treści...');
    const select = document.getElementById('machine-select');
    if (select && select.value) await loadChartData(select.value);
    await loadInspirationsData();
    await loadSlidesData();
    await loadContent();
}

// ==================== EKSPORTOWANE FUNKCJE ====================

window.showSection = showSection;
window.toggleDarkMode = toggleDarkMode;
window.goToSlide = goToSlide;
window.toggleAutoRotation = toggleAutoRotation;
