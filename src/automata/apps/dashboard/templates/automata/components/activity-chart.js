import { Base } from '/lib/adaptive-ui.js';

export async function loadChartLibrary() {
  try { return await import('/lib/echarts.js'); } catch { return null; }
}

const color = name => getComputedStyle(document.documentElement).getPropertyValue(`--anatomy-chart-${name}`).trim();
const format = (stamp, timezone, options) => new Intl.DateTimeFormat(undefined, { timeZone: timezone, ...options }).format(new Date(stamp));

class AnatomyChart extends Base {
  #data = { rows: [], timeline: [], available: false, timezone: 'Asia/Bangkok' };
  #chart;
  #observer;
  #library;
  static { this.css = 'display:block; width:100%; min-width:0;'; }
  static validateData(value) {
    if (!Array.isArray(value.rows) || !Array.isArray(value.timeline) ||
      !value.rows.every(row => typeof row.name === 'string' && Number.isInteger(row.count) && row.count >= 0) ||
      !value.timeline.every(bucket => Number.isInteger(bucket.count) && bucket.count >= 0)) throw new Error('Invalid chart data');
    return value;
  }
  applyData(value) { this.#data = AnatomyChart.validateData(value); this.#draw(); }
  connectedCallback() {
    super.connectedCallback();
    this.#observer ??= new ResizeObserver(() => this.#chart?.resize());
    this.#observer.observe(this);
    this.#connect();
  }
  async #connect() {
    this.#library = await loadChartLibrary();
    if (this.isConnected) this.#draw();
  }
  disconnectedCallback() {
    this.#observer?.disconnect();
    this.#chart?.dispose(); this.#chart = null;
    super.disconnectedCallback?.();
  }
  redraw() { this.#draw(); }
  #draw() {
    if (!this.isConnected) return;
    const { rows, timeline, available, timezone, bucket } = this.#data;
    const series = this.mode === 'timeline' ? timeline : rows;
    if (!this.#library || !available || !series.length) {
      this.#chart?.dispose(); this.#chart = null;
      this.style.height = 'auto';
      this.textContent = !this.#library ? 'Chart unavailable; data and counts remain accessible.'
        : !available ? 'Recording unavailable.' : 'No recorded events in this window.';
      return;
    }
    const isTimeline = this.mode === 'timeline';
    this.style.height = (isTimeline ? 280 : Math.max(200, rows.length * 34 + 70)) + 'px';
    if (!this.#chart) { this.textContent = ''; this.#chart = this.#library.init(this, null, { renderer: 'canvas' }); }
    this.#chart.resize();
    const text = color('text'); const grid = color('grid');
    const label = interval => format(interval.start, timezone, {
      month: 'short', day: 'numeric',
      ...(bucket === 'hour' ? { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' } : {}),
    });
    this.#chart.setOption({
      animation: false,
      aria: { enabled: true, description: isTimeline ? 'Recorded loads over time.' : 'Recorded skill loads ranked by count. A data table follows.' },
      grid: { left: 12, right: 40, top: 22, bottom: isTimeline ? 48 : 32, containLabel: true },
      textStyle: { color: text },
      tooltip: { trigger: 'item', renderMode: 'richText', confine: true,
        backgroundColor: color('tooltip-bg'), textStyle: { color: color('tooltip-text') },
        formatter: params => isTimeline
          ? `${label(timeline[params.dataIndex])} · ${timezone}\n${params.value} recorded loads`
          : `${params.name}\n${params.value} recorded loads\nLatest: ${params.data.latest ? format(params.data.latest, timezone, { dateStyle: 'medium', timeStyle: 'short' }) : 'Unknown'} (${timezone})` },
      xAxis: isTimeline
        ? { type: 'category', data: timeline.map(label), axisLabel: { color: text, hideOverlap: true, rotate: timeline.length > 20 ? 35 : 0 }, axisLine: { lineStyle: { color: grid } } }
        : { type: 'value', minInterval: 1, axisLabel: { color: text }, splitLine: { lineStyle: { color: grid } } },
      yAxis: isTimeline
        ? { type: 'value', minInterval: 1, axisLabel: { color: text }, splitLine: { lineStyle: { color: grid } } }
        : { type: 'category', inverse: true, data: rows.map(row => row.name), axisLabel: { color: text, width: this.clientWidth < 600 ? 125 : 270, overflow: 'truncate' }, axisLine: { lineStyle: { color: grid } } },
      series: isTimeline
        ? [{ type: 'line', showSymbol: timeline.length < 32, symbolSize: 6, lineStyle: { color: color('line'), width: 2 }, itemStyle: { color: color('line') }, areaStyle: { color: color('bar'), opacity: .12 }, data: timeline.map(bucket => bucket.count) }]
        : [{ type: 'bar', barMaxWidth: 22, label: { show: true, position: 'right', color: text }, itemStyle: { color: color('bar') }, data: rows.map(row => ({ value: row.count, latest: row.latest })) }],
    }, { notMerge: true });
  }
}
export class SkillLoadsChart extends AnatomyChart { mode = 'ranking'; }
export class SkillTimelineChart extends AnatomyChart { mode = 'timeline'; }
SkillLoadsChart.define('skill-loads-chart');
SkillTimelineChart.define('skill-timeline-chart');
