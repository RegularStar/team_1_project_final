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

  class BarChart {
    constructor(canvas, options) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.baseOptions = Object.assign(
        {
          yLabelSuffix: '명',
          suggestedMax: null,
          yTicks: 4,
          padding: { top: 32, right: 32, bottom: 110, left: 76 }
        },
        options || {}
      );
      this.currentOptions = Object.assign({}, this.baseOptions);
      this.items = [];
      this.hasData = false;
    }

    setData(items, overrideOptions) {
      const normalized = [];
      (Array.isArray(items) ? items : []).forEach((item) => {
        if (!item || item.value === null || item.value === undefined) {
          return;
        }
        const labelText = String(item.label ?? '').trim();
        if (!labelText) {
          return;
        }
        const numericValue = Number(item.value);
        if (!Number.isFinite(numericValue)) {
          return;
        }
        normalized.push({
          label: labelText,
          value: numericValue,
          fill: item.fill || (item.highlight ? '#7aa2ff' : 'rgba(122, 162, 255, 0.28)'),
          stroke: item.stroke || (item.highlight ? 'rgba(122, 162, 255, 0.9)' : 'rgba(122, 162, 255, 0.2)'),
          highlight: Boolean(item.highlight)
        });
      });
      this.items = normalized;
      this.hasData = this.items.length > 0;
      this.currentOptions = Object.assign({}, this.baseOptions, overrideOptions || {});
      this.redraw();
    }

    redraw() {
      if (!this.canvas) {
        return;
      }
      const width = Math.floor(this.canvas.clientWidth);
      const height = Math.floor(this.canvas.clientHeight || 360);
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

      const options = this.currentOptions;
      const padding = options.padding || { top: 32, right: 32, bottom: 110, left: 76 };
      const plotWidth = Math.max(1, width - padding.left - padding.right);
      const plotHeight = Math.max(1, height - padding.top - padding.bottom);

      const values = this.items.map((item) => item.value).filter((value) => Number.isFinite(value));
      let yMax = options.suggestedMax;
      if (!Number.isFinite(yMax)) {
        yMax = values.length ? Math.max(...values) : 0;
      } else if (values.length) {
        yMax = Math.max(yMax, ...values);
      }
      if (!Number.isFinite(yMax) || yMax <= 0) {
        yMax = options.yLabelSuffix === '%' ? 100 : 1;
      }

      const yTicks = Math.max(1, options.yTicks || 4);

      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.fillStyle = 'rgba(231, 237, 247, 0.85)';
      ctx.font = '12px "Apple SD Gothic Neo", "Segoe UI", sans-serif';

      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let i = 0; i <= yTicks; i += 1) {
        const ratio = i / yTicks;
        const y = padding.top + plotHeight - ratio * plotHeight;
        ctx.beginPath();
        ctx.moveTo(padding.left - 6, y);
        ctx.lineTo(padding.left + plotWidth, y);
        ctx.stroke();
        const value = ratio * yMax;
        const displayValue = options.yLabelSuffix === '%' ? value : Math.round(value);
        ctx.fillText(formatNumber(displayValue, options.yLabelSuffix), padding.left - 10, y);
      }

      const count = this.items.length;
      if (!count) {
        ctx.restore();
        return;
      }

      const step = plotWidth / count;
      const barWidth = Math.max(12, Math.min(64, step * 0.55));
      const textColor = 'rgba(231, 237, 247, 0.88)';

      this.items.forEach((item, index) => {
        const centerX = padding.left + step * index + step / 2;
        const ratio = yMax ? Math.min(item.value / yMax, 1) : 0;
        const barHeight = Math.max(0, ratio * plotHeight);
        const x = centerX - barWidth / 2;
        const y = padding.top + plotHeight - barHeight;

        ctx.fillStyle = item.fill;
        ctx.fillRect(x, y, barWidth, barHeight);
        if (barHeight > 0.5) {
          ctx.strokeStyle = item.stroke;
          ctx.lineWidth = item.highlight ? 1.6 : 1;
          ctx.strokeRect(x, y, barWidth, barHeight);
        }

        ctx.fillStyle = textColor;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(formatNumber(item.value, options.yLabelSuffix), centerX, y - 6);

        ctx.save();
        ctx.translate(centerX, padding.top + plotHeight + 8);
        ctx.rotate(-Math.PI / 4.5);
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = 'rgba(204, 214, 235, 0.85)';
        ctx.fillText(item.label, 0, 0);
        ctx.restore();
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

  const tagComparisons = Array.isArray(stats.tagComparisons) ? stats.tagComparisons : [];
  const tagSelect = document.querySelector('[data-tag-comparison-tag]');
  const tagSessionSelect = document.querySelector('[data-tag-comparison-session]');
  const tagYearSelect = document.querySelector('[data-tag-comparison-year]');
  const tagMetricSelect = document.querySelector('[data-tag-comparison-metric]');
  const tagChartCanvas = document.getElementById('tag-comparison-chart');
  const tagCard = document.querySelector('[data-tag-comparison-card]');
  const tagEmpty = document.querySelector('[data-tag-comparison-empty]');
  const tagLegend = document.querySelector('[data-tag-comparison-legend]');
  const tagTitle = document.querySelector('[data-tag-comparison-title]');

  const tagMetricConfig = {
    applicants: { label: '응시자수', suffix: '명' },
    pass_rate: { label: '합격률', suffix: '%', suggestedMax: 100 },
    registered: { label: '접수자수', suffix: '명' },
    passers: { label: '합격자수', suffix: '명' }
  };

  const tagDataMap = new Map();
  tagComparisons.forEach((entry) => {
    if (entry && entry.id !== undefined && entry.id !== null) {
      const key = String(entry.id);
      const normalized = Object.assign({}, entry, {
        sessions: Array.isArray(entry.sessions) ? entry.sessions : []
      });
      tagDataMap.set(key, normalized);
    }
  });

  function getTagEntry(tagId) {
    if (tagId === null || tagId === undefined) {
      return null;
    }
    return tagDataMap.get(String(tagId)) || null;
  }

  function getSessionEntry(tagEntry, sessionKey) {
    if (!tagEntry || !sessionKey) {
      return null;
    }
    return (tagEntry.sessions || []).find((session) => session.key === sessionKey) || null;
  }

  function setEmptySelect(selectElement, placeholder) {
    if (!selectElement) {
      return;
    }
    selectElement.innerHTML = '';
    const option = document.createElement('option');
    option.value = '';
    option.textContent = placeholder;
    selectElement.appendChild(option);
    selectElement.value = '';
    selectElement.disabled = true;
  }

  function populateSessionOptions(tagEntry) {
    if (!tagSessionSelect) {
      return null;
    }
    tagSessionSelect.innerHTML = '';
    if (!tagEntry || !Array.isArray(tagEntry.sessions) || tagEntry.sessions.length === 0) {
      setEmptySelect(tagSessionSelect, '데이터 없음');
      return null;
    }
    tagSessionSelect.disabled = false;
    let defaultKey = tagEntry.defaultSessionKey || null;
    tagEntry.sessions.forEach((session, index) => {
      const option = document.createElement('option');
      option.value = session.key;
      option.textContent = session.label || session.key || '차수';
      if ((defaultKey && session.key === defaultKey) || (!defaultKey && index === 0)) {
        option.selected = true;
        defaultKey = session.key;
      }
      tagSessionSelect.appendChild(option);
    });
    if (defaultKey) {
      tagSessionSelect.value = defaultKey;
    }
    return tagSessionSelect.value || defaultKey || null;
  }

  function populateYearOptions(tagEntry, sessionKey) {
    if (!tagYearSelect) {
      return null;
    }
    tagYearSelect.innerHTML = '';
    const sessionEntry = getSessionEntry(tagEntry, sessionKey);
    if (!sessionEntry || !Array.isArray(sessionEntry.years) || sessionEntry.years.length === 0) {
      setEmptySelect(tagYearSelect, '연도 없음');
      return null;
    }

    tagYearSelect.disabled = false;
    const years = sessionEntry.years.slice();
    years.forEach((year) => {
      const option = document.createElement('option');
      option.value = year;
      option.textContent = year;
      tagYearSelect.appendChild(option);
    });

    let defaultYear = null;
    if (tagEntry?.defaultYear && years.includes(tagEntry.defaultYear)) {
      defaultYear = tagEntry.defaultYear;
    }
    if (!defaultYear) {
      defaultYear = years[years.length - 1];
    }
    if (defaultYear) {
      tagYearSelect.value = defaultYear;
    }
    return tagYearSelect.value || defaultYear || null;
  }

  function buildBarItems(tagEntry, sessionKey, year, metricKey) {
    const sessionEntry = getSessionEntry(tagEntry, sessionKey);
    if (!sessionEntry || !year) {
      return [];
    }
    const metricsList = sessionEntry.metrics ? sessionEntry.metrics[year] : null;
    if (!Array.isArray(metricsList)) {
      return [];
    }

    const sortable = metricsList.slice();
    sortable.sort((a, b) => {
      const aValueRaw = a ? a[metricKey] : null;
      const bValueRaw = b ? b[metricKey] : null;
      const aValue = Number(aValueRaw);
      const bValue = Number(bValueRaw);
      const safeA = Number.isFinite(aValue) ? aValue : Number.NEGATIVE_INFINITY;
      const safeB = Number.isFinite(bValue) ? bValue : Number.NEGATIVE_INFINITY;
      return safeB - safeA;
    });

    const items = [];
    let primaryItem = null;
    sortable.forEach((row) => {
      if (!row) {
        return;
      }
      const valueRaw = row[metricKey];
      if (valueRaw === null || valueRaw === undefined) {
        return;
      }
      const numericValue = Number(valueRaw);
      if (!Number.isFinite(numericValue)) {
        return;
      }
      const label = String(row.title ?? '').trim();
      if (!label) {
        return;
      }
      const item = {
        label,
        value: numericValue,
        highlight: Boolean(row.isPrimary)
      };
      items.push(item);
      if (row.isPrimary) {
        primaryItem = item;
      }
    });

    const maxBars = 12;
    let trimmed = items.slice(0, maxBars);
    if (primaryItem && !trimmed.some((item) => item.highlight)) {
      if (trimmed.length >= maxBars) {
        trimmed.pop();
      }
      trimmed.push(primaryItem);
    }
    trimmed.sort((a, b) => b.value - a.value);
    return trimmed;
  }

  function renderTagLegend() {
    if (!tagLegend) {
      return;
    }
    tagLegend.innerHTML = '';
    const primary = document.createElement('span');
    primary.className = 'chart-legend-item';
    primary.innerHTML = '<span class="legend-dot" style="--dot-color: #7aa2ff"></span>현재 자격증';
    tagLegend.appendChild(primary);
    const peer = document.createElement('span');
    peer.className = 'chart-legend-item';
    peer.innerHTML = '<span class="legend-dot" style="--dot-color: rgba(122, 162, 255, 0.28)"></span>연관 자격증';
    tagLegend.appendChild(peer);
  }

  let tagChart = null;
  if (tagChartCanvas) {
    tagChart = new BarChart(tagChartCanvas, { yTicks: 4 });
    charts.push(tagChart);
  }

  function updateTagChart() {
    if (!tagChart) {
      return;
    }
    const tagEntry = getTagEntry(tagSelect ? tagSelect.value : null);
    const metricKey = tagMetricSelect ? tagMetricSelect.value : 'applicants';
    const metricMeta = tagMetricConfig[metricKey] || tagMetricConfig.applicants;
    const sessionKey = tagSessionSelect ? tagSessionSelect.value || null : null;
    const yearValue = tagYearSelect ? tagYearSelect.value || null : null;

    const items = tagEntry ? buildBarItems(tagEntry, sessionKey, yearValue, metricKey) : [];
    tagChart.setData(items, {
      yLabelSuffix: metricMeta.suffix,
      suggestedMax: metricMeta.suggestedMax ?? null
    });
    toggleEmptyState(tagCard, tagEmpty, tagChart.hasData);

    if (tagTitle) {
      if (tagEntry) {
        const sessionEntry = getSessionEntry(tagEntry, sessionKey);
        const sessionLabel = sessionEntry ? sessionEntry.label : '차수 데이터 없음';
        const yearLabel = yearValue || '연도 데이터 없음';
        tagTitle.textContent = `${tagEntry.name} 태그 · ${sessionLabel} · ${yearLabel} · ${metricMeta.label}`;
      } else {
        tagTitle.textContent = '태그 기반 비교';
      }
    }
  }

  function applyTag(tagId) {
    const tagEntry = getTagEntry(tagId);
    const sessionKey = populateSessionOptions(tagEntry);
    populateYearOptions(tagEntry, sessionKey);
    updateTagChart();
  }

  function initializeTagComparison() {
    if (!tagSelect) {
      return;
    }
    const initialTagId = tagSelect.value || (tagComparisons.length ? String(tagComparisons[0].id) : null);
    if (initialTagId) {
      tagSelect.value = initialTagId;
      applyTag(initialTagId);
    } else {
      updateTagChart();
    }
  }

  if (tagChart && tagSelect && tagComparisons.length) {
    renderTagLegend();
    initializeTagComparison();

    tagSelect.addEventListener('change', () => {
      applyTag(tagSelect.value);
    });

    if (tagSessionSelect) {
      tagSessionSelect.addEventListener('change', () => {
        const currentTag = getTagEntry(tagSelect ? tagSelect.value : null);
        populateYearOptions(currentTag, tagSessionSelect.value || null);
        updateTagChart();
      });
    }

    if (tagYearSelect) {
      tagYearSelect.addEventListener('change', () => {
        updateTagChart();
      });
    }

    if (tagMetricSelect) {
      tagMetricSelect.addEventListener('change', () => {
        updateTagChart();
      });
    }
  } else if (tagChart) {
    tagChart.setData([]);
    toggleEmptyState(tagCard, tagEmpty, false);
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
