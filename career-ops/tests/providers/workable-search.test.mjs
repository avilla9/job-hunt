// tests/providers/workable-search.test.mjs — provider-contract tests for the
// Jobs by Workable cross-employer search (providers/workable-search.mjs).
import { pass, fail, ROOT } from '../helpers.mjs';
import { join } from 'path';
import { pathToFileURL } from 'url';

console.log('\nProvider — workable-search');

const check = (ok, msg) => (ok ? pass(msg) : fail(msg));

try {
  const mod = await import(pathToFileURL(join(ROOT, 'providers/workable-search.mjs')).href);
  const provider = mod.default;
  const { normalizeWorkableJob, buildWorkableUrl } = mod;

  check(provider.id === 'workable-search', 'id is "workable-search"');

  const row = {
    title: ' Senior Engineer ', url: 'https://jobs.workable.com/view/abc/senior-engineer', description: '<p>Build &amp; ship</p>',
    locations: ['TELECOMMUTE'], location: { city: '', countryName: 'Colombia' }, created: '2026-09-25T10:00:00Z',
    company: { title: 'Acme' }, workplace: 'remote',
  };
  const job = normalizeWorkableJob(row);
  check(job?.title === 'Senior Engineer' && job.company === 'Acme', 'normalizes title and company');
  check(job?.location === 'Remote · Colombia', 'location uses country over TELECOMMUTE and flags remote');
  check(job?.description === 'Build & ship', 'description is HTML-to-text with entities decoded');
  check(job?.postedAt === Date.parse('2026-09-25T10:00:00Z'), 'postedAt from created');
  check(normalizeWorkableJob({ ...row, created: 'nope' }).postedAt === undefined, 'bad date is NaN-safe');
  check(normalizeWorkableJob({ ...row, url: 'https://evil.example/view/x' }) === null, 'drops off-host URLs');
  check(normalizeWorkableJob({ ...row, title: '' }) === null, 'drops rows without title');

  const url = new URL(buildWorkableUrl({ search: 'Full Stack', location: 'Latin America', workplace: 'remote' }, 'tok'));
  check(url.origin === 'https://jobs.workable.com' && url.searchParams.get('query') === 'Full Stack'
    && url.searchParams.get('location') === 'Latin America' && url.searchParams.get('workplace') === 'remote'
    && url.searchParams.get('pageToken') === 'tok', 'builds the search URL');
  let threw = false;
  try { buildWorkableUrl({ search: '' }); } catch { threw = true; }
  check(threw, 'rejects an entry without search');
  threw = false;
  try { buildWorkableUrl({ search: 'x', workplace: 'moon' }); } catch { threw = true; }
  check(threw, 'rejects an unknown workplace');

  const fakeCtx = (pages) => {
    const calls = [];
    return {
      calls,
      sleep: async () => {},
      fetchJson: async (u, opts) => {
        calls.push({ u, opts });
        return pages[calls.length - 1];
      },
    };
  };
  const page = (n, token) => ({ jobs: [{ ...row, url: `https://jobs.workable.com/view/${n}/x` }], nextPageToken: token });

  let ctx = fakeCtx([page(1, 't1'), page(2, 't2'), page(3, '')]);
  let jobs = await provider.fetch({ search: 'x', max_pages: 10 }, ctx);
  check(jobs.length === 3 && ctx.calls.length === 3, 'follows nextPageToken until it runs out');
  check(ctx.calls.every(c => c.opts.redirect === 'error'), 'every request sets redirect: error');

  ctx = fakeCtx([page(1, 't1'), page(2, 't2'), page(3, 't3'), page(4, 't4')]);
  await provider.fetch({ search: 'x' }, ctx);
  check(ctx.calls.length === 3, 'stops at DEFAULT_MAX_PAGES even when the source has more');

  ctx = fakeCtx([page(1, 't1'), page(2, 't2')]);
  ctx.maxPages = 1;
  await provider.fetch({ search: 'x' }, ctx);
  check(ctx.calls.length === 1, 'health probe (maxPages: 1) makes exactly one request');

  ctx = fakeCtx([{ error: 'bad' }]);
  threw = false;
  try { await provider.fetch({ search: 'x' }, ctx); } catch (e) { threw = /jobs/.test(e.message); }
  check(threw, 'throws naming the keys on an unexpected envelope');

  ctx = fakeCtx([{ jobs: [] }]);
  jobs = await provider.fetch({ search: 'x' }, ctx);
  check(Array.isArray(jobs) && jobs.length === 0, 'empty jobs array returns []');
} catch (e) {
  fail(`workable-search tests crashed: ${e.message}`);
}
