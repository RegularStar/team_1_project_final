(function () {
  const dataElement = document.getElementById('certificate-statistics-data');
  if (!dataElement) {
    return;
  }

  let stats;
  try {
    stats = JSON.parse(dataElement.textContent || '{}');
  } catch (error) {
    console.error('통계 데이터를 불러오는 중 오류가 발생했습니다.', error);
    return;
  }

  if (!stats || !Array.isArray(stats.years) || stats.years.length === 0) {
    return;
  }

  const years = stats.years;
  const charts = [];

  const palette = {
    registered: '#7aa2ff',
    registeredLight: 'rgba(122, 162, 255, 0.28)',
    applicants: '#3ddc84',
    applicantsLight: 'rgba(61, 220, 132, 0.28)',
    passers: '#ffb74d',
    passersLight: 'rgba(255, 183, 77, 0.28)',
    passRate: '#b388ff',
    passRateLight: 'rgba(179, 136, 255, 0.28)'
  };

  function formatNumber(value, suffix) {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return '-';
    }
    if (suffix === '%') {
      return `${Number(value).toFixed(1)}%`;
    }
    return `${Number(value).toLocaleString('ko-KR')}${suffix ?? ''}`;
  }

  function datasetHasData(dataset) {
    return Array.isArray(dataset?.data) && dataset.data.some((value) => Number.isFinite(value));
  }

  function seriesHasData(series) {
    if (!Array.isArray(series)) {
      return false;
    }
    return series.some((dataset) => datasetHasData(dataset));
  }

  class LineChart {
    constructor(canvas, labels, options) {
      this.canvas = canvas;
      this.labels = labels;
      this.options = Object.assign(
        {
          yLabelSuffix: '명',
          suggestedMax: null,
          yTicks: 4,
          padding: { top: 28, right: 24, bottom: 40, left: 64 }
        },
        options || {}
      );
      this.ctx = canvas.getContext('2d');
      this.datasets = [];
      this.legendElement = null;
      this.hasData = false;
    }

    setDatasets(datasets) {
      this.datasets = Array.isArray(datasets) ? datasets : [];
      this.hasData = seriesHasData(this.datasets);
      this.renderLegend();
      this.redraw();
    }

    renderLegend() {
      const container = this.canvas.closest('.chart-card');
      if (!container) {
        return;
      }

      let legend = container.querySelector('.chart-legend');
      if (!legend) {
        legend = document.createElement('div');
        legend.className = 'chart-legend';
        container.insertBefore(legend, this.canvas);
      }

      legend.innerHTML = '';
      this.datasets.forEach((dataset) => {
        if (!dataset?.label) {
          return;
        }
        const item = document.createElement('span');
        item.className = 'chart-legend-item';
        item.innerHTML = `<span class="legend-dot" style="--dot-color: ${dataset.color || '#7aa2ff'}"></span>${dataset.label}`;
        legend.appendChild(item);
      });
      this.legendElement = legend;
    }

    redraw() {
      const width = Math.floor(this.canvas.clientWidth);
      const height = Math.floor(this.canvas.clientHeight || 320);
      if (!width || !height) {
        return;
      }

      const dpr = window.devicePixelRatio || 1;
      if (this.canvas.width !== width * dpr || this.canvas.height !== height * dpr) {
        this.canvas.width = width * dpr;
        this.canvas.height = height * dpr;
      }

      const ctx = this.ctx;
      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      const padding = this.options.padding;
      const plotWidth = Math.max(1, width - padding.left - padding.right);
      const plotHeight = Math.max(1, height - padding.top - padding.bottom);

      const allValues = [];
      this.datasets.forEach((dataset) => {
        if (!Array.isArray(dataset?.data)) {
          return;
        }
        dataset.data.forEach((value) => {
          if (Number.isFinite(value)) {
            allValues.push(Number(value));
          }
        });
      });

      let yMax = this.options.suggestedMax;
      if (!Number.isFinite(yMax)) {
        yMax = Math.max(...allValues, 0);
      } else {
        yMax = Math.max(yMax, ...allValues);
      }
      if (!Number.isFinite(yMax) || yMax <= 0) {
        yMax = this.options.yLabelSuffix === '%' ? 100 : 1;
      }

      const yMin = 0;
      const yRange = Math.max(1, yMax - yMin);
      const tickCount = Math.max(1, this.options.yTicks);

      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.fillStyle = 'rgba(231, 237, 247, 0.85)';
      ctx.font = '12px "Apple SD Gothic Neo", "Segoe UI", sans-serif';

      // Grid lines and y-axis labels
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let i = 0; i <= tickCount; i += 1) {
        const ratio = i / tickCount;
        const y = padding.top + plotHeight - ratio * plotHeight;
        ctx.beginPath();
        ctx.moveTo(padding.left - 6, y);
        ctx.lineTo(padding.left + plotWidth, y);
        ctx.stroke();
        const value = yMin + ratio * yRange;
        ctx.fillText(
          formatNumber(this.options.yLabelSuffix === '%' ? value : Math.round(value), this.options.yLabelSuffix),
          padding.left - 10,
          y
        );
      }

      // x-axis labels
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const xCount = this.labels.length;
      const step = xCount > 1 ? plotWidth / (xCount - 1) : 0;
      for (let i = 0; i < xCount; i += 1) {
        const x = padding.left + (xCount > 1 ? step * i : plotWidth / 2);
        const label = this.labels[i];
        ctx.fillText(label, x, padding.top + plotHeight + 12);
      }

      // Draw datasets
      this.datasets.forEach((dataset) => {
        if (!Array.isArray(dataset?.data)) {
          return;
        }
        ctx.lineWidth = 2.4;
        ctx.strokeStyle = dataset.color || '#7aa2ff';
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        let hasStarted = false;
        ctx.beginPath();
        dataset.data.forEach((value, index) => {
          if (!Number.isFinite(value)) {
            hasStarted = false;
            return;
          }
          const x = padding.left + (xCount > 1 ? step * index : plotWidth / 2);
          const y = padding.top + plotHeight - ((value - yMin) / yRange) * plotHeight;
          if (!hasStarted) {
            ctx.moveTo(x, y);
            hasStarted = true;
          } else {
            ctx.lineTo(x, y);
          }
        });
        ctx.stroke();

        // Draw points
        dataset.data.forEach((value, index) => {
          if (!Number.isFinite(value)) {
            return;
          }
          const x = padding.left + (xCount > 1 ? step * index : plotWidth / 2);
          const y = padding.top + plotHeight - ((value - yMin) / yRange) * plotHeight;
          ctx.beginPath();
          ctx.fillStyle = dataset.color || '#7aa2ff';
          ctx.arc(x, y, 3.2, 0, Math.PI * 2);
          ctx.fill();
        });
      });

      ctx.restore();
    }
  }

  function makeDataset(label, data, color, suffix = '명') {
    return {
      label,
      data: Array.isArray(data) ? data.map((value) => (value === null || value === undefined ? null : Number(value))) : [],
      color,
      suffix
    };
  }

  function buildVolumeDatasets(series) {
    return [
      makeDataset('접수자수', series?.registered, palette.registered),
      makeDataset('응시자수', series?.applicants, palette.applicants),
      makeDataset('합격자수', series?.passers, palette.passers)
    ];
  }

  function buildRateDataset(series) {
    return [makeDataset('합격률', series?.pass_rate, palette.passRate, '%')];
  }

  function toggleEmptyState(card, placeholder, hasData) {
    if (!card || !placeholder) {
      return;
    }
    if (hasData) {
      card.classList.remove('is-empty');
      placeholder.hidden = true;
    } else {
      card.classList.add('is-empty');
      placeholder.hidden = false;
    }
  }

  const sessionVolumeCanvas = document.getElementById('session-volume-chart');
  const sessionRateCanvas = document.getElementById('session-pass-rate-chart');
  const sessionVolumeCard = document.querySelector('[data-session-volume-card]');
  const sessionRateCard = document.querySelector('[data-session-rate-card]');
  const sessionVolumeEmpty = document.querySelector('[data-session-volume-empty]');
  const sessionRateEmpty = document.querySelector('[data-session-rate-empty]');

  const sessionSeriesMap = new Map();
  const sessionMetricsMap = new Map();
  if (Array.isArray(stats.sessions)) {
    stats.sessions.forEach((session) => {
      sessionSeriesMap.set(session.key, session.series || {});
      sessionMetricsMap.set(session.key, session.metrics || {});
    });
  }

  let sessionVolumeChart = null;
  if (sessionVolumeCanvas) {
    sessionVolumeChart = new LineChart(sessionVolumeCanvas, years, { yLabelSuffix: '명', yTicks: 4 });
    sessionVolumeChart.setDatasets([]);
    charts.push(sessionVolumeChart);
  }

  let sessionRateChart = null;
  if (sessionRateCanvas) {
    sessionRateChart = new LineChart(sessionRateCanvas, years, { yLabelSuffix: '%', suggestedMax: 100, yTicks: 4 });
    sessionRateChart.setDatasets([]);
    charts.push(sessionRateChart);
  }

  const summaryYearSelect = document.querySelector('[data-summary-year]');
  const summaryEmpty = document.querySelector('[data-summary-empty]');
  const summaryTargets = {
    registered: document.querySelector('[data-summary-metric="registered"]'),
    applicants: document.querySelector('[data-summary-metric="applicants"]'),
    passers: document.querySelector('[data-summary-metric="passers"]'),
    pass_rate: document.querySelector('[data-summary-metric="pass_rate"]')
  };

  function updateSummary(sessionKey) {
    if (!summaryYearSelect) {
      return;
    }

    const year = summaryYearSelect.value;
    const metricsByYear = sessionMetricsMap.get(sessionKey) || {};
    const metrics = metricsByYear ? metricsByYear[year] : null;

    const fields = [
      { key: 'registered', suffix: '명' },
      { key: 'applicants', suffix: '명' },
      { key: 'passers', suffix: '명' },
      { key: 'pass_rate', suffix: '%' }
    ];

    let hasData = false;
    fields.forEach((field) => {
      const target = summaryTargets[field.key];
      if (!target) {
        return;
      }
      const value = metrics ? metrics[field.key] : null;
      if (value !== null && value !== undefined) {
        hasData = true;
      }
      target.textContent = formatNumber(value, field.suffix);
    });

    if (summaryEmpty) {
      summaryEmpty.hidden = hasData;
    }
  }

  const sessionButtons = Array.from(document.querySelectorAll('[data-session-key]'));

  function updateSessionCharts(sessionKey) {
    const series = sessionSeriesMap.get(sessionKey) || {};
    if (sessionVolumeChart) {
      sessionVolumeChart.setDatasets(buildVolumeDatasets(series));
      toggleEmptyState(sessionVolumeCard, sessionVolumeEmpty, sessionVolumeChart.hasData);
    }
    if (sessionRateChart) {
      sessionRateChart.setDatasets(buildRateDataset(series));
      toggleEmptyState(sessionRateCard, sessionRateEmpty, sessionRateChart.hasData);
    }
  }

  function applySessionState(sessionKey) {
    sessionButtons.forEach((button) => {
      const isActive = button.dataset.sessionKey === sessionKey;
      button.classList.toggle('is-active', isActive);
      if (button.hasAttribute('aria-selected')) {
        button.setAttribute('aria-selected', isActive ? 'true' : 'false');
      }
    });
  }

  let activeSessionKey = null;
  if (sessionButtons.length) {
    const preselected = sessionButtons.find((button) => button.classList.contains('is-active'));
    activeSessionKey = preselected ? preselected.dataset.sessionKey : sessionButtons[0].dataset.sessionKey;
  }

  function handleSessionChange(sessionKey) {
    activeSessionKey = sessionKey;
    applySessionState(sessionKey);
    updateSessionCharts(sessionKey);
    updateSummary(sessionKey);
  }

  sessionButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const { sessionKey } = button.dataset;
      if (!sessionKey || sessionKey === activeSessionKey) {
        return;
      }
      handleSessionChange(sessionKey);
    });
  });

  if (summaryYearSelect) {
    summaryYearSelect.addEventListener('change', () => {
      updateSummary(activeSessionKey);
    });
  }

  if (activeSessionKey) {
    handleSessionChange(activeSessionKey);
  } else {
    updateSessionCharts(null);
    updateSummary(null);
  }

  let resizeTimeout = null;
  window.addEventListener('resize', () => {
    if (resizeTimeout) {
      cancelAnimationFrame(resizeTimeout);
    }
    resizeTimeout = requestAnimationFrame(() => {
      charts.forEach((chart) => chart.redraw());
    });
  });
})();
