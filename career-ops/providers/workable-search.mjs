// @ts-check
/** @typedef {import('./_types.js').Provider} Provider */

// Jobs by Workable — the cross-employer search at https://jobs.workable.com
// (→ job_boards:). Distinct from workable.mjs, which reads ONE employer's
// apply.workable.com account; this one searches every Workable employer.
//
//   GET https://jobs.workable.com/api/v1/jobs?query=<q>[&location=<place>][&workplace=remote|hybrid|on_site][&pageToken=<t>]
//   → { totalSize, nextPageToken, jobs: [{ id, title, description (HTML), url, locations, location:{city,countryName},
//        created, company:{title}, workplace }] }
//
// Public, no auth. 20 rows per page, cursor pagination via nextPageToken. The
// description ships in the list payload, so it is populated for free.
// Explicit-only: reached by `provider: workable-search` in portals.yml, with
// `search` (required), optional `location`, `workplace`, `max_pages`.

import { htmlToText } from './_html-to-text.mjs';
import { BROWSER_LIKE_USER_AGENT, fetchJsonWithRetry, sleep } from './_http.mjs';

const API = 'https://jobs.workable.com/api/v1/jobs';
const TRUSTED_HOST = 'jobs.workable.com';
const DEFAULT_MAX_PAGES = 3;
const MAX_PAGES_CAP = 25;
const PAGE_DELAY_MS = 500;
const WORKPLACES = new Set(['remote', 'hybrid', 'on_site']);

function resolveMaxPages(entry) {
  const v = entry?.max_pages;
  if (Number.isInteger(v) && v > 0) return Math.min(v, MAX_PAGES_CAP);
  return DEFAULT_MAX_PAGES;
}

/** @param {string} raw */
function trustedUrl(raw) {
  try {
    const u = new URL(String(raw || ''));
    return u.protocol === 'https:' && u.hostname === TRUSTED_HOST ? u.href : '';
  } catch {
    return '';
  }
}

function toEpochMs(value) {
  const ms = Date.parse(String(value || ''));
  return Number.isFinite(ms) ? ms : undefined;
}

export function normalizeWorkableJob(j) {
  if (!j || typeof j !== 'object') return null;
  const title = typeof j.title === 'string' ? j.title.trim() : '';
  const url = trustedUrl(j.url);
  if (!title || !url) return null;
  // locations[0] is often the literal "TELECOMMUTE" on remote rows; city/country is the informative part.
  const place = [j.location?.city, j.location?.countryName].filter(Boolean).join(', ')
    || (Array.isArray(j.locations) && typeof j.locations[0] === 'string' ? j.locations[0] : '');
  const location = [j.workplace === 'remote' ? 'Remote' : '', place].filter(Boolean).join(' · ');
  const job = { title, url, company: String(j.company?.title || '').trim(), location };
  const description = typeof j.description === 'string' ? htmlToText(j.description) : '';
  if (description) job.description = description;
  const postedAt = toEpochMs(j.created);
  if (postedAt !== undefined) job.postedAt = postedAt;
  return job;
}

export function buildWorkableUrl(entry, pageToken) {
  const search = typeof entry?.search === 'string' ? entry.search.trim() : '';
  if (!search) throw new Error('workable-search: entry needs a non-empty `search`');
  const params = new URLSearchParams({ query: search });
  if (typeof entry.location === 'string' && entry.location.trim()) params.set('location', entry.location.trim());
  if (entry.workplace != null) {
    if (!WORKPLACES.has(entry.workplace)) throw new Error(`workable-search: workplace must be one of ${[...WORKPLACES].join(', ')}`);
    params.set('workplace', entry.workplace);
  }
  if (pageToken) params.set('pageToken', pageToken);
  return `${API}?${params}`;
}

/** @type {Provider} */
export default {
  id: 'workable-search',

  async fetch(entry, ctx) {
    const ctxMaxPages = Number(ctx?.maxPages);
    const pages = Math.min(resolveMaxPages(entry), ctxMaxPages > 0 ? ctxMaxPages : Infinity);
    const out = [];
    const seen = new Set();
    let token = '';
    for (let page = 0; page < pages; page++) {
      if (page > 0) await sleep(PAGE_DELAY_MS, ctx);
      const json = await fetchJsonWithRetry(ctx, buildWorkableUrl(entry, token), {
        headers: { 'user-agent': BROWSER_LIKE_USER_AGENT, accept: 'application/json' },
        redirect: 'error',
      });
      if (!json || typeof json !== 'object' || !Array.isArray(json.jobs)) {
        throw new Error(`workable-search: unexpected response — expected { jobs: [...] }, got keys: [${json && typeof json === 'object' ? Object.keys(json).join(', ') : typeof json}]`);
      }
      for (const raw of json.jobs) {
        const job = normalizeWorkableJob(raw);
        if (!job || seen.has(job.url)) continue;
        seen.add(job.url);
        out.push(job);
      }
      token = typeof json.nextPageToken === 'string' ? json.nextPageToken : '';
      if (!token || json.jobs.length === 0) break;
    }
    return out;
  },
};
