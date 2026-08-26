#!/usr/bin/env node

import { createHash } from "node:crypto";
import {
  createReadStream,
  createWriteStream,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { pathToFileURL } from "node:url";

const VERSION = "1.0.0";
const MAIN_ORIGIN = "https://www.centralbank.ie";
const OPEN_DATA_ORIGIN = "https://opendata.centralbank.ie";
const OFFICIAL_REDIRECT_HOSTS = new Set([
  "cbi-prod-filestore-public.s3.amazonaws.com",
]);
const SITEMAP_URL = `${MAIN_ORIGIN}/sitemap/sitemap.xml`;
const CKAN_SEARCH_URL = `${OPEN_DATA_ORIGIN}/api/3/action/package_search?rows=1000`;
const DEFAULT_TYPES = [
  "pdf", "csv", "xlsx", "xls", "docx", "doc", "zip", "json", "xml",
  "ods", "pptx", "ppt", "txt", "rtf", "tsv", "parquet", "geojson",
];
const ASSET_TYPES = [
  "jpg", "jpeg", "png", "gif", "svg", "webp", "avif", "mp3", "mp4",
  "wav", "webm", "css", "js", "woff", "woff2", "ttf", "eot",
];
const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
const WINDOWS_RESERVED = new Set([
  "CON", "PRN", "AUX", "NUL",
  ...Array.from({ length: 9 }, (_, i) => `COM${i + 1}`),
  ...Array.from({ length: 9 }, (_, i) => `LPT${i + 1}`),
]);

function usage() {
  return `
CBI Public Archive ${VERSION}

Inventory and download public material from centralbank.ie without using private portals.

Usage:
  node cbi-archive.mjs probe [options]
  node cbi-archive.mjs inventory [options]
  node cbi-archive.mjs download [options]
  node cbi-archive.mjs repair [options]
  node cbi-archive.mjs report [options]

Commands:
  probe       Fetch robots.txt, count sitemap pages, and total CKAN resources.
  inventory   Save CKAN metadata and crawl sitemap pages for linked documents.
  download    Download pending files from an existing inventory; safe to resume.
  repair      Replace recoverable malformed quoted links with canonical document URLs.
  report      Rebuild CSV/JSONL manifests and print a summary.

Common options:
  --out DIR             Archive directory (default: ./cbi-data)
  --delay-ms N          Minimum delay between requests (default: 1000)
  --timeout-ms N        Request timeout (default: 30000)
  --retries N           Retry count for transient failures (default: 4)
  --contact TEXT        Contact URL/email appended to the User-Agent

Inventory options:
  --scope all|opendata|documents  (default: all)
  --max-pages N         Page crawl cap; 0 means all (default: 100)
  --path-prefix PATH    Only crawl sitemap pages under this URL path
  --types LIST          Comma-separated extensions to discover
  --include-assets      Also discover images, media, CSS, JS, and fonts
  --refresh-pages       Re-fetch pages already inventoried

Download options:
  --only all|opendata|documents   (default: all)
  --max-files N         Download cap; 0 means unlimited (default: 0)
  --max-bytes N         Byte cap; 0 means unlimited; accepts 500M, 10G
  --retry-failed        Retry records previously marked failed

Examples:
  node cbi-archive.mjs probe
  node cbi-archive.mjs inventory --scope opendata --out ./cbi-data
  node cbi-archive.mjs download --only opendata --out ./cbi-data
  node cbi-archive.mjs inventory --scope all --max-pages 0 --out ./cbi-data
  node cbi-archive.mjs download --out ./cbi-data --max-bytes 20G
`.trim();
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      args._.push(token);
      continue;
    }
    if (token.startsWith("--no-")) {
      args[toCamel(token.slice(5))] = false;
      continue;
    }
    const equals = token.indexOf("=");
    if (equals !== -1) {
      args[toCamel(token.slice(2, equals))] = token.slice(equals + 1);
      continue;
    }
    const key = toCamel(token.slice(2));
    const next = argv[i + 1];
    if (next !== undefined && !next.startsWith("--")) {
      args[key] = next;
      i += 1;
    } else {
      args[key] = true;
    }
  }
  return args;
}

function toCamel(value) {
  return value.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}

function nonNegativeInt(value, fallback, name) {
  if (value === undefined) return fallback;
  const number = Number(value);
  if (!Number.isInteger(number) || number < 0) {
    throw new Error(`${name} must be a non-negative integer`);
  }
  return number;
}

function parseBytes(value) {
  if (value === undefined || value === null || value === "") return 0;
  const match = String(value).trim().match(/^(\d+(?:\.\d+)?)\s*([kmgt]?i?b?)?$/i);
  if (!match) throw new Error(`Invalid byte limit: ${value}`);
  const units = { "": 1, b: 1, k: 1024, kb: 1024, kib: 1024, m: 1024 ** 2, mb: 1024 ** 2, mib: 1024 ** 2, g: 1024 ** 3, gb: 1024 ** 3, gib: 1024 ** 3, t: 1024 ** 4, tb: 1024 ** 4, tib: 1024 ** 4 };
  return Math.floor(Number(match[1]) * units[match[2].toLowerCase()]);
}

function formatBytes(bytes) {
  if (!Number.isFinite(Number(bytes))) return "unknown";
  const number = Number(bytes);
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let index = 0;
  let value = number;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
}

class ByteLimitError extends Error {
  constructor(limit) {
    super(`Download byte cap reached after ${formatBytes(limit)} of response data`);
    this.name = "ByteLimitError";
  }
}

function byteLimitTransform(limit) {
  let transferred = 0;
  return new Transform({
    transform(chunk, encoding, callback) {
      if (limit > 0 && transferred + chunk.length > limit) {
        callback(new ByteLimitError(limit));
        return;
      }
      transferred += chunk.length;
      callback(null, chunk);
    },
  });
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

class RateLimiter {
  constructor(delayMs) {
    this.delayMs = delayMs;
    this.lastStarted = 0;
  }

  async wait() {
    const remaining = this.delayMs - (Date.now() - this.lastStarted);
    if (remaining > 0) await sleep(remaining);
    this.lastStarted = Date.now();
  }
}

function createContext(options = {}) {
  const delayMs = nonNegativeInt(options.delayMs, 1000, "--delay-ms");
  const timeoutMs = nonNegativeInt(options.timeoutMs, 30000, "--timeout-ms");
  const retries = nonNegativeInt(options.retries, 4, "--retries");
  const contact = options.contact ? `; ${options.contact}` : "";
  return {
    delayMs,
    timeoutMs,
    retries,
    userAgent: `CBI-Public-Archive/${VERSION} (public-data research${contact})`,
    limiter: new RateLimiter(delayMs),
  };
}

function retryAfterMs(value) {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, date - Date.now());
}

async function fetchWithRetry(url, context, options = {}) {
  let lastError;
  for (let attempt = 0; attempt <= context.retries; attempt += 1) {
    await context.limiter.wait();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), context.timeoutMs);
    try {
      const response = await fetch(url, {
        ...options,
        redirect: "follow",
        signal: controller.signal,
        headers: {
          "user-agent": context.userAgent,
          accept: "*/*",
          ...(options.headers || {}),
        },
      });
      clearTimeout(timer);
      if (!isAllowedResponseHost(new URL(response.url).hostname)) {
        await response.body?.cancel();
        throw new Error(`Refusing redirect outside Central Bank domains: ${response.url}`);
      }
      if (RETRYABLE_STATUS.has(response.status) && attempt < context.retries) {
        const waitMs = retryAfterMs(response.headers.get("retry-after")) ?? Math.min(30000, 1000 * (2 ** attempt));
        await response.body?.cancel();
        console.warn(`HTTP ${response.status} for ${url}; retrying in ${waitMs} ms`);
        await sleep(waitMs);
        continue;
      }
      return response;
    } catch (error) {
      clearTimeout(timer);
      lastError = error;
      if (attempt >= context.retries) break;
      const waitMs = Math.min(30000, 1000 * (2 ** attempt));
      console.warn(`${error.name || "RequestError"} for ${url}; retrying in ${waitMs} ms`);
      await sleep(waitMs);
    }
  }
  throw lastError ?? new Error(`Request failed: ${url}`);
}

async function fetchText(url, context, options) {
  const response = await fetchWithRetry(url, context, options);
  if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}: ${url}`);
  return { response, text: await response.text() };
}

function parseRobots(text) {
  const groups = [];
  let group = { agents: [], rules: [] };
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/\s*#.*$/, "").trim();
    if (!line) continue;
    const colon = line.indexOf(":");
    if (colon === -1) continue;
    const field = line.slice(0, colon).trim().toLowerCase();
    const value = line.slice(colon + 1).trim();
    if (field === "user-agent") {
      if (group.rules.length > 0) {
        groups.push(group);
        group = { agents: [], rules: [] };
      }
      group.agents.push(value.toLowerCase());
    } else if ((field === "allow" || field === "disallow") && group.agents.length > 0) {
      if (value || field === "allow") group.rules.push({ allow: field === "allow", pattern: value });
    }
  }
  if (group.agents.length > 0) groups.push(group);
  return groups;
}

function robotsPatternMatches(pattern, target) {
  if (pattern === "") return false;
  const anchored = pattern.endsWith("$");
  const body = anchored ? pattern.slice(0, -1) : pattern;
  const escaped = body.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*");
  return new RegExp(`^${escaped}${anchored ? "$" : ""}`).test(target);
}

function robotsAllows(groups, url, userAgent = "cbi-public-archive") {
  const token = userAgent.toLowerCase();
  let bestSpecificity = -1;
  let matchingGroups = [];
  for (const group of groups) {
    const matches = group.agents
      .filter((agent) => agent === "*" || token.includes(agent))
      .map((agent) => (agent === "*" ? 0 : agent.length));
    if (matches.length === 0) continue;
    const specificity = Math.max(...matches);
    if (specificity > bestSpecificity) {
      bestSpecificity = specificity;
      matchingGroups = [group];
    } else if (specificity === bestSpecificity) {
      matchingGroups.push(group);
    }
  }
  if (matchingGroups.length === 0) return true;
  const target = `${new URL(url).pathname}${new URL(url).search}`;
  const matchingRules = matchingGroups.flatMap((group) => group.rules)
    .filter((rule) => robotsPatternMatches(rule.pattern, target))
    .sort((a, b) => b.pattern.length - a.pattern.length || Number(b.allow) - Number(a.allow));
  return matchingRules.length === 0 ? true : matchingRules[0].allow;
}

function decodeXml(value) {
  return value
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'");
}

function extractSitemapLocations(xml) {
  return [...xml.matchAll(/<loc>\s*([^<]+?)\s*<\/loc>/gi)].map((match) => decodeXml(match[1].trim()));
}

function decodeHtml(value) {
  return value
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&#x2F;/gi, "/")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">");
}

function extractLinks(html, baseUrl) {
  const links = new Set();
  const attributePattern = /\b(?:href|src|data-src|data-href)\s*=\s*(?:"([^"]+)"|'([^']+)'|([^\s>]+))/gi;
  for (const match of html.matchAll(attributePattern)) {
    let raw = decodeHtml(match[1] ?? match[2] ?? match[3] ?? "").trim();
    if ((raw.startsWith('"') || raw.startsWith("'")) && raw.length > 1) {
      const quote = raw[0];
      raw = raw.slice(1);
      const closing = raw.indexOf(quote);
      if (closing !== -1) raw = raw.slice(0, closing);
    }
    if (!raw || raw.startsWith("#") || /^(?:mailto|tel|javascript|data):/i.test(raw)) continue;
    try {
      const resolved = new URL(raw, baseUrl);
      if (resolved.protocol === "http:" || resolved.protocol === "https:") {
        resolved.hash = "";
        links.add(resolved.href);
      }
    } catch {
      // Ignore malformed links on source pages.
    }
  }
  return [...links];
}

function extensionForUrl(url) {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(url).pathname).toLowerCase();
  } catch {
    return "";
  }
  const match = pathname.match(/\.([a-z0-9]{1,10})$/i);
  return match ? match[1].toLowerCase() : "";
}

function canonicalUrl(url) {
  const parsed = new URL(url);
  parsed.hash = "";
  parsed.hostname = parsed.hostname.toLowerCase();
  parsed.searchParams.sort();
  return parsed.href;
}

function isCentralBankHost(hostname) {
  const host = hostname.toLowerCase();
  return host === "centralbank.ie" || host === "www.centralbank.ie" || host === "opendata.centralbank.ie";
}

function isAllowedResponseHost(hostname) {
  const host = hostname.toLowerCase();
  return isCentralBankHost(host) || OFFICIAL_REDIRECT_HOSTS.has(host);
}

function isFileCandidate(url, types) {
  try {
    const parsed = new URL(url);
    if (!isCentralBankHost(parsed.hostname)) return false;
    const extension = extensionForUrl(url);
    return types.has(extension);
  } catch {
    return false;
  }
}

function shortHash(value, length = 12) {
  return createHash("sha256").update(value).digest("hex").slice(0, length);
}

function safeSegment(value) {
  let decoded = value;
  try { decoded = decodeURIComponent(value); } catch { /* retain encoded text */ }
  let safe = decoded.replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").replace(/[. ]+$/g, "").trim();
  if (!safe) safe = "_";
  if (WINDOWS_RESERVED.has(safe.toUpperCase())) safe = `_${safe}`;
  if (safe.length > 90) {
    const extension = path.extname(safe);
    const stem = safe.slice(0, Math.max(1, 70 - extension.length));
    safe = `${stem}__${shortHash(decoded, 10)}${extension}`;
  }
  return safe;
}

function filePathForUrl(rootDirectory, url) {
  const parsed = new URL(url);
  const host = safeSegment(parsed.hostname.toLowerCase());
  const rawSegments = parsed.pathname.split("/").filter(Boolean);
  let segments = rawSegments.map(safeSegment);
  if (segments.length === 0) segments = ["index.html"];
  if (parsed.search) {
    const final = segments.at(-1);
    const extension = path.extname(final);
    const stem = final.slice(0, final.length - extension.length);
    segments[segments.length - 1] = `${stem}__q-${shortHash(parsed.search, 10)}${extension}`;
  }
  {
    const final = segments.at(-1);
    const extension = path.extname(final);
    const stem = final.slice(0, final.length - extension.length);
    segments[segments.length - 1] = `${stem}__u-${shortHash(canonicalUrl(parsed.href), 12)}${extension}`;
  }
  let relative = path.join(host, ...segments);
  const filesRoot = path.join(path.resolve(rootDirectory), "files");
  const maxRelativeLength = Math.max(70, 230 - filesRoot.length - 1);
  if (relative.length > maxRelativeLength) {
    const final = segments.at(-1);
    const extension = path.extname(final);
    const fixedLength = path.join(host, "_long", shortHash(parsed.href, 24), "x").length - 1 + extension.length;
    const availableStem = Math.max(4, maxRelativeLength - fixedLength);
    const stem = final.slice(0, Math.max(1, final.length - extension.length)).slice(0, availableStem);
    relative = path.join(host, "_long", shortHash(parsed.href, 24), `${stem}${extension}`);
  }
  return path.join(filesRoot, relative);
}

function atomicWrite(filename, contents) {
  mkdirSync(path.dirname(filename), { recursive: true });
  const temporary = `${filename}.tmp`;
  writeFileSync(temporary, contents);
  if (existsSync(filename)) unlinkSync(filename);
  renameSync(temporary, filename);
}

function statePath(outDirectory) {
  return path.join(outDirectory, "archive-state.json");
}

function newState() {
  const now = new Date().toISOString();
  return {
    schemaVersion: 1,
    toolVersion: VERSION,
    createdAt: now,
    updatedAt: now,
    sources: {},
    sitemap: { urls: [], fetchedAt: null },
    ckan: { datasetCount: 0, resourceCount: 0, fetchedAt: null },
    pages: {},
    files: {},
  };
}

function loadState(outDirectory, required = false) {
  const filename = statePath(outDirectory);
  if (!existsSync(filename)) {
    if (required) throw new Error(`No inventory found at ${filename}. Run the inventory command first.`);
    return newState();
  }
  const state = JSON.parse(readFileSync(filename, "utf8"));
  state.pages ||= {};
  state.files ||= {};
  state.sources ||= {};
  return state;
}

function saveState(outDirectory, state) {
  state.updatedAt = new Date().toISOString();
  atomicWrite(statePath(outDirectory), `${JSON.stringify(state, null, 2)}\n`);
}

function addFile(state, url, details = {}) {
  const key = canonicalUrl(url);
  const existing = state.files[key];
  const source = details.source || "documents";
  if (existing) {
    existing.sources ||= [existing.source || source];
    if (!existing.sources.includes(source)) existing.sources.push(source);
    if (details.referrer) {
      existing.referrers ||= [];
      if (existing.referrers.length < 20 && !existing.referrers.includes(details.referrer)) existing.referrers.push(details.referrer);
    }
    for (const field of ["expectedBytes", "format", "datasetId", "datasetTitle", "resourceId", "resourceName", "licenseTitle", "licenseUrl"]) {
      if (details[field] !== undefined && details[field] !== null && details[field] !== "") existing[field] = details[field];
    }
    return false;
  }
  state.files[key] = {
    url: key,
    source,
    sources: [source],
    referrers: details.referrer ? [details.referrer] : [],
    extension: extensionForUrl(key),
    format: details.format || extensionForUrl(key).toUpperCase(),
    expectedBytes: Number.isFinite(Number(details.expectedBytes)) ? Number(details.expectedBytes) : null,
    datasetId: details.datasetId || null,
    datasetTitle: details.datasetTitle || null,
    resourceId: details.resourceId || null,
    resourceName: details.resourceName || null,
    licenseTitle: details.licenseTitle || null,
    licenseUrl: details.licenseUrl || null,
    discoveredAt: new Date().toISOString(),
    status: "pending",
    attempts: 0,
    localPath: null,
    downloadedBytes: null,
    sha256: null,
    contentType: null,
    etag: null,
    lastModified: null,
    error: null,
  };
  return true;
}

function csvEscape(value) {
  if (value === null || value === undefined) return "";
  const text = Array.isArray(value) ? value.join(" | ") : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function summarize(state) {
  const files = Object.values(state.files);
  const statuses = {};
  const formats = {};
  const sources = {};
  let knownBytes = 0;
  let downloadedBytes = 0;
  for (const file of files) {
    statuses[file.status] = (statuses[file.status] || 0) + 1;
    const format = file.format || file.extension || "unknown";
    formats[format] = (formats[format] || 0) + 1;
    for (const source of file.sources || [file.source]) sources[source] = (sources[source] || 0) + 1;
    if (Number.isFinite(Number(file.expectedBytes))) knownBytes += Number(file.expectedBytes);
    if (Number.isFinite(Number(file.downloadedBytes))) downloadedBytes += Number(file.downloadedBytes);
  }
  const pageStatuses = {};
  for (const page of Object.values(state.pages)) pageStatuses[page.status] = (pageStatuses[page.status] || 0) + 1;
  return {
    generatedAt: new Date().toISOString(),
    sitemapUrls: state.sitemap?.urls?.length || 0,
    ckanDatasets: state.ckan?.datasetCount || 0,
    ckanResources: state.ckan?.resourceCount || 0,
    files: files.length,
    statuses,
    formats,
    sources,
    knownBytes,
    knownBytesHuman: formatBytes(knownBytes),
    downloadedBytes,
    downloadedBytesHuman: formatBytes(downloadedBytes),
    pageStatuses,
  };
}

function writeManifests(outDirectory, state) {
  const manifestDirectory = path.join(outDirectory, "manifests");
  mkdirSync(manifestDirectory, { recursive: true });
  const files = Object.values(state.files).sort((a, b) => a.url.localeCompare(b.url));
  atomicWrite(path.join(manifestDirectory, "files.jsonl"), `${files.map((file) => JSON.stringify(file)).join("\n")}${files.length ? "\n" : ""}`);
  const fields = [
    "url", "status", "source", "sources", "format", "expectedBytes", "downloadedBytes",
    "sha256", "localPath", "datasetTitle", "resourceName", "licenseTitle", "licenseUrl",
    "contentType", "etag", "lastModified", "referrers", "error",
  ];
  const rows = [fields.join(",")];
  for (const file of files) rows.push(fields.map((field) => csvEscape(file[field])).join(","));
  atomicWrite(path.join(manifestDirectory, "files.csv"), `${rows.join("\r\n")}\r\n`);
  const failedFields = ["url", "error", "attempts", "referrers", "malformedSourceUrls"];
  const failedRows = [failedFields.join(",")];
  for (const file of files.filter((file) => file.status === "failed")) {
    failedRows.push(failedFields.map((field) => csvEscape(file[field])).join(","));
  }
  atomicWrite(path.join(manifestDirectory, "failed-urls.csv"), `${failedRows.join("\r\n")}\r\n`);
  const summary = summarize(state);
  atomicWrite(path.join(manifestDirectory, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
  return summary;
}

function printSummary(summary) {
  console.log(`Sitemap pages:       ${summary.sitemapUrls}`);
  console.log(`CKAN datasets:       ${summary.ckanDatasets}`);
  console.log(`CKAN resources:      ${summary.ckanResources}`);
  console.log(`Discovered files:    ${summary.files}`);
  console.log(`Published size est.: ${summary.knownBytesHuman}`);
  console.log(`Downloaded:          ${summary.downloadedBytesHuman}`);
  console.log(`File status:         ${JSON.stringify(summary.statuses)}`);
  console.log(`Page crawl status:   ${JSON.stringify(summary.pageStatuses)}`);
}

async function fetchRobots(origin, context) {
  const url = `${origin}/robots.txt`;
  const { text, response } = await fetchText(url, context, { headers: { accept: "text/plain" } });
  return { url, text, rules: parseRobots(text), fetchedAt: new Date().toISOString(), status: response.status };
}

async function discoverSitemap(url, context, robots, seen = new Set()) {
  if (seen.has(url)) return [];
  if (seen.size >= 100) throw new Error("Sitemap index contains more than 100 sitemap files; refusing unbounded expansion");
  seen.add(url);
  if (robots && !robotsAllows(robots.rules, url)) throw new Error(`robots.txt disallows sitemap URL: ${url}`);
  const { text } = await fetchText(url, context, { headers: { accept: "application/xml,text/xml" } });
  const locations = extractSitemapLocations(text);
  if (/<sitemapindex\b/i.test(text)) {
    const nested = [];
    for (const location of locations) nested.push(...await discoverSitemap(location, context, robots, seen));
    return nested;
  }
  return locations;
}

async function discoverCkan(state, outDirectory, context) {
  const { text } = await fetchText(CKAN_SEARCH_URL, context, { headers: { accept: "application/json" } });
  const payload = JSON.parse(text);
  if (!payload.success || !payload.result) throw new Error("CKAN package_search returned an unsuccessful response");
  const packages = payload.result.results || [];
  mkdirSync(path.join(outDirectory, "metadata"), { recursive: true });
  atomicWrite(path.join(outDirectory, "metadata", "ckan-packages.json"), `${JSON.stringify(packages, null, 2)}\n`);
  let resources = 0;
  for (const dataset of packages) {
    for (const resource of dataset.resources || []) {
      if (!resource.url || !/^https?:/i.test(resource.url)) continue;
      resources += 1;
      addFile(state, resource.url, {
        source: "opendata",
        format: resource.format || resource.mimetype || extensionForUrl(resource.url).toUpperCase(),
        expectedBytes: resource.size,
        datasetId: dataset.id,
        datasetTitle: dataset.title,
        resourceId: resource.id,
        resourceName: resource.name,
        licenseTitle: dataset.license_title,
        licenseUrl: dataset.license_url,
        referrer: `${OPEN_DATA_ORIGIN}/dataset/${dataset.id}`,
      });
    }
  }
  state.ckan = {
    datasetCount: payload.result.count ?? packages.length,
    resourceCount: resources,
    fetchedAt: new Date().toISOString(),
    apiUrl: CKAN_SEARCH_URL,
  };
  return { datasets: packages.length, resources };
}

function selectedTypes(options) {
  const values = options.types ? String(options.types).split(",") : DEFAULT_TYPES;
  const types = new Set(values.map((value) => value.trim().toLowerCase().replace(/^\./, "")).filter(Boolean));
  if (options.includeAssets) for (const type of ASSET_TYPES) types.add(type);
  return types;
}

function validScope(value) {
  const scope = value || "all";
  if (!new Set(["all", "opendata", "documents"]).has(scope)) throw new Error(`Invalid scope: ${scope}`);
  return scope;
}

async function probe(options) {
  const context = createContext(options);
  console.log(`User-Agent: ${context.userAgent}`);
  const mainRobots = await fetchRobots(MAIN_ORIGIN, context);
  console.log(`robots.txt: ${mainRobots.status}; ${mainRobots.rules.flatMap((group) => group.rules).length} allow/disallow rules`);
  const sitemapUrls = await discoverSitemap(SITEMAP_URL, context, mainRobots);
  console.log(`Sitemap: ${sitemapUrls.length} URLs`);
  const { text } = await fetchText(CKAN_SEARCH_URL, context, { headers: { accept: "application/json" } });
  const payload = JSON.parse(text);
  const packages = payload.result?.results || [];
  const resources = packages.flatMap((dataset) => dataset.resources || []);
  const knownBytes = resources.reduce((sum, resource) => sum + (Number(resource.size) || 0), 0);
  console.log(`Open Data API: ${payload.result?.count ?? packages.length} datasets; ${resources.length} resources; ${formatBytes(knownBytes)} published size estimate`);
}

async function inventory(options) {
  const context = createContext(options);
  const outDirectory = path.resolve(String(options.out || "cbi-data"));
  const scope = validScope(options.scope);
  const maxPages = nonNegativeInt(options.maxPages, 100, "--max-pages");
  const types = selectedTypes(options);
  mkdirSync(outDirectory, { recursive: true });
  const state = loadState(outDirectory);
  state.toolVersion = VERSION;
  state.settings = {
    scope,
    delayMs: context.delayMs,
    types: [...types].sort(),
    pathPrefix: options.pathPrefix || null,
  };
  console.log(`Archive: ${outDirectory}`);
  console.log(`User-Agent: ${context.userAgent}`);

  const mainRobots = await fetchRobots(MAIN_ORIGIN, context);
  state.sources[MAIN_ORIGIN] = { robotsUrl: mainRobots.url, robotsText: mainRobots.text, fetchedAt: mainRobots.fetchedAt };
  let openDataRobots = null;
  if (scope === "all" || scope === "opendata") {
    try {
      openDataRobots = await fetchRobots(OPEN_DATA_ORIGIN, context);
      state.sources[OPEN_DATA_ORIGIN] = { robotsUrl: openDataRobots.url, robotsText: openDataRobots.text, fetchedAt: openDataRobots.fetchedAt };
    } catch (error) {
      console.warn(`Could not fetch Open Data robots.txt: ${error.message}`);
    }
    const result = await discoverCkan(state, outDirectory, context);
    console.log(`Inventoried ${result.datasets} CKAN datasets with ${result.resources} resources.`);
    saveState(outDirectory, state);
  }

  if (scope === "all" || scope === "documents") {
    console.log("Fetching sitemap...");
    const sitemapUrls = await discoverSitemap(SITEMAP_URL, context, mainRobots);
    state.sitemap = { urls: sitemapUrls, fetchedAt: new Date().toISOString(), source: SITEMAP_URL };
    let candidates = sitemapUrls.filter((url) => {
      try {
        const parsed = new URL(url);
        if (!isCentralBankHost(parsed.hostname)) return false;
        return options.pathPrefix ? parsed.pathname.startsWith(String(options.pathPrefix)) : true;
      } catch { return false; }
    });
    if (!options.refreshPages) candidates = candidates.filter((url) => state.pages[canonicalUrl(url)]?.status !== "done");
    if (maxPages > 0) candidates = candidates.slice(0, maxPages);
    console.log(`Crawling ${candidates.length} page(s) at >=${context.delayMs} ms/request. ${maxPages === 0 ? "Full crawl selected." : `Cap: ${maxPages}.`}`);
    let pagesSinceSave = 0;
    let newFiles = 0;
    for (let index = 0; index < candidates.length; index += 1) {
      const url = canonicalUrl(candidates[index]);
      if (!robotsAllows(mainRobots.rules, url)) {
        state.pages[url] = { status: "blocked-by-robots", checkedAt: new Date().toISOString() };
        continue;
      }
      try {
        const { text, response } = await fetchText(url, context, { headers: { accept: "text/html,application/xhtml+xml" } });
        const links = extractLinks(text, response.url || url);
        let discovered = 0;
        for (const link of links) {
          if (isFileCandidate(link, types)) {
            if (addFile(state, link, { source: "documents", referrer: url })) {
              discovered += 1;
              newFiles += 1;
            }
          }
        }
        state.pages[url] = {
          status: "done",
          httpStatus: response.status,
          checkedAt: new Date().toISOString(),
          links: links.length,
          filesDiscovered: discovered,
        };
      } catch (error) {
        state.pages[url] = { status: "failed", checkedAt: new Date().toISOString(), error: error.message };
        console.warn(`Page failed: ${url}: ${error.message}`);
      }
      pagesSinceSave += 1;
      if (pagesSinceSave >= 50) {
        saveState(outDirectory, state);
        writeManifests(outDirectory, state);
        pagesSinceSave = 0;
        console.log(`[${index + 1}/${candidates.length}] ${newFiles} new files discovered`);
      }
    }
  }

  saveState(outDirectory, state);
  const summary = writeManifests(outDirectory, state);
  printSummary(summary);
  console.log(`Manifest: ${path.join(outDirectory, "manifests", "files.csv")}`);
}

async function sha256File(filename) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(filename)) hash.update(chunk);
  return hash.digest("hex");
}

function storedRobotsForOrigin(state, origin) {
  const text = state.sources?.[origin]?.robotsText;
  return text ? parseRobots(text) : null;
}

function sourceMatches(file, only) {
  if (only === "all") return true;
  return (file.sources || [file.source]).includes(only);
}

async function downloadOne(file, outDirectory, context, robotsByOrigin, maxNewBytes = 0) {
  const parsed = new URL(file.url);
  const origin = parsed.origin;
  const rules = robotsByOrigin.get(origin);
  if (rules && !robotsAllows(rules, file.url)) {
    file.status = "blocked-by-robots";
    file.error = "robots.txt disallows this URL";
    return { downloaded: false, bytes: 0 };
  }
  const destination = filePathForUrl(outDirectory, file.url);
  const part = `${destination}.part`;
  mkdirSync(path.dirname(destination), { recursive: true });
  if (existsSync(destination)) {
    const size = statSync(destination).size;
    file.status = "downloaded";
    file.localPath = path.relative(outDirectory, destination);
    file.downloadedBytes = size;
    file.sha256 ||= await sha256File(destination);
    file.error = null;
    return { downloaded: false, bytes: 0 };
  }
  const partialBytes = existsSync(part) ? statSync(part).size : 0;
  const headers = {};
  if (partialBytes > 0) headers.range = `bytes=${partialBytes}-`;
  file.attempts = (file.attempts || 0) + 1;
  const response = await fetchWithRetry(file.url, context, { headers });
  if (response.status === 416 && partialBytes > 0) {
    renameSync(part, destination);
  } else {
    if (!response.ok) {
      await response.body?.cancel();
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    const append = partialBytes > 0 && response.status === 206;
    if (!response.body) throw new Error("Response has no body");
    const responseBytes = Number(response.headers.get("content-length"));
    if (maxNewBytes > 0 && Number.isFinite(responseBytes) && responseBytes > maxNewBytes) {
      await response.body.cancel();
      throw new ByteLimitError(maxNewBytes);
    }
    const source = Readable.fromWeb(response.body);
    if (maxNewBytes > 0) {
      await pipeline(source, byteLimitTransform(maxNewBytes), createWriteStream(part, { flags: append ? "a" : "w" }));
    } else {
      await pipeline(source, createWriteStream(part, { flags: append ? "a" : "w" }));
    }
    renameSync(part, destination);
  }
  const size = statSync(destination).size;
  file.status = "downloaded";
  file.localPath = path.relative(outDirectory, destination);
  file.downloadedBytes = size;
  file.sha256 = await sha256File(destination);
  file.contentType = response.headers.get("content-type");
  file.etag = response.headers.get("etag");
  file.lastModified = response.headers.get("last-modified");
  file.downloadedAt = new Date().toISOString();
  file.error = null;
  if (Number.isFinite(Number(file.expectedBytes)) && Number(file.expectedBytes) !== size) {
    file.sizeWarning = `Expected ${file.expectedBytes} bytes from metadata; downloaded ${size}`;
  } else {
    file.sizeWarning = null;
  }
  return { downloaded: true, bytes: size };
}

async function download(options) {
  const context = createContext(options);
  const outDirectory = path.resolve(String(options.out || "cbi-data"));
  const state = loadState(outDirectory, true);
  const only = validScope(options.only);
  const maxFiles = nonNegativeInt(options.maxFiles, 0, "--max-files");
  const maxBytes = parseBytes(options.maxBytes);
  const robotsByOrigin = new Map();
  for (const origin of [MAIN_ORIGIN, OPEN_DATA_ORIGIN]) {
    let rules = storedRobotsForOrigin(state, origin);
    try {
      const live = await fetchRobots(origin, context);
      rules = live.rules;
      state.sources[origin] = { robotsUrl: live.url, robotsText: live.text, fetchedAt: live.fetchedAt };
    } catch (error) {
      if (!rules) throw new Error(`Cannot verify robots.txt for ${origin}: ${error.message}`);
      console.warn(`Using cached robots.txt for ${origin}: ${error.message}`);
    }
    robotsByOrigin.set(origin, rules);
  }
  let candidates = Object.values(state.files).filter((file) => {
    if (!sourceMatches(file, only)) return false;
    if (file.status === "pending") return true;
    return Boolean(options.retryFailed) && file.status === "failed";
  });
  if (maxFiles > 0) candidates = candidates.slice(0, maxFiles);
  console.log(`Archive: ${outDirectory}`);
  console.log(`Pending selection: ${candidates.length} file(s); delay >=${context.delayMs} ms/request; byte cap ${maxBytes ? formatBytes(maxBytes) : "unlimited"}`);
  let filesDownloaded = 0;
  let bytesDownloaded = 0;
  let sinceStateCheckpoint = 0;
  let sinceManifestCheckpoint = 0;
  let lastStateCheckpoint = Date.now();
  for (let index = 0; index < candidates.length; index += 1) {
    const file = candidates[index];
    if (maxBytes > 0 && bytesDownloaded >= maxBytes) break;
    if (maxBytes > 0 && file.expectedBytes && bytesDownloaded + file.expectedBytes > maxBytes) {
      console.log(`Stopping before byte cap; next known file is ${formatBytes(file.expectedBytes)}.`);
      break;
    }
    try {
      const remainingBytes = maxBytes > 0 ? maxBytes - bytesDownloaded : 0;
      const result = await downloadOne(file, outDirectory, context, robotsByOrigin, remainingBytes);
      if (result.downloaded) {
        filesDownloaded += 1;
        bytesDownloaded += result.bytes;
      }
      if ((index + 1) % 25 === 0 || file.status !== "downloaded") {
        console.log(`[${index + 1}/${candidates.length}] ${file.status} ${formatBytes(file.downloadedBytes)} ${file.url}`);
      }
    } catch (error) {
      if (error instanceof ByteLimitError) {
        file.status = "pending";
        file.error = `${error.message}; rerun with a larger --max-bytes value to resume`;
        console.log(`Paused at byte cap while downloading ${file.url}`);
        saveState(outDirectory, state);
        writeManifests(outDirectory, state);
        break;
      }
      file.status = "failed";
      file.error = error.message;
      file.failedAt = new Date().toISOString();
      console.warn(`[${index + 1}/${candidates.length}] failed ${file.url}: ${error.message}`);
    }
    sinceStateCheckpoint += 1;
    sinceManifestCheckpoint += 1;
    if (sinceStateCheckpoint >= 50 || Date.now() - lastStateCheckpoint >= 60000) {
      saveState(outDirectory, state);
      sinceStateCheckpoint = 0;
      lastStateCheckpoint = Date.now();
    }
    if (sinceManifestCheckpoint >= 250) {
      writeManifests(outDirectory, state);
      sinceManifestCheckpoint = 0;
    }
  }
  saveState(outDirectory, state);
  const summary = writeManifests(outDirectory, state);
  console.log(`This run: ${filesDownloaded} file(s), ${formatBytes(bytesDownloaded)}`);
  printSummary(summary);
}

async function report(options) {
  const outDirectory = path.resolve(String(options.out || "cbi-data"));
  const state = loadState(outDirectory, true);
  const summary = writeManifests(outDirectory, state);
  printSummary(summary);
  console.log(`CSV manifest: ${path.join(outDirectory, "manifests", "files.csv")}`);
}

function repairMalformedUrl(url) {
  let original;
  let decodedPath;
  try {
    original = new URL(url);
    decodedPath = decodeURIComponent(original.pathname);
  } catch { return null; }
  const start = decodedPath.toLowerCase().indexOf("/docs/default-source/");
  if (start === -1) return null;
  const candidatePath = decodedPath.slice(start).split(/["'<>]/, 1)[0].trim();
  if (!candidatePath || !extensionForUrl(new URL(candidatePath, MAIN_ORIGIN).href)) return null;
  try {
    const parsed = new URL(candidatePath, MAIN_ORIGIN);
    for (const [name, value] of original.searchParams) {
      let cleaned = value.split(/["'<>]/, 1)[0].replace(/&amp;.*$/i, "");
      if (name.toLowerCase() === "sfvrsn") cleaned = cleaned.replace(/https?:\/\/.*$/i, "");
      if (cleaned) parsed.searchParams.append(name, cleaned);
    }
    const repaired = canonicalUrl(parsed.href);
    return repaired === canonicalUrl(url) ? null : repaired;
  } catch { return null; }
}

function revisionAliasKey(url) {
  try {
    const parsed = new URL(url);
    const revision = parsed.searchParams.get("sfvrsn");
    if (!revision) return null;
    const basename = decodeURIComponent(parsed.pathname.split("/").pop() || "").toLowerCase();
    return basename ? `${basename}\n${revision}` : null;
  } catch {
    return null;
  }
}

async function repair(options) {
  const outDirectory = path.resolve(String(options.out || "cbi-data"));
  const state = loadState(outDirectory, true);
  const downloadedByRevision = new Map();
  for (const file of Object.values(state.files)) {
    if (file.status !== "downloaded") continue;
    const aliasKey = revisionAliasKey(file.url);
    if (!aliasKey) continue;
    const matches = downloadedByRevision.get(aliasKey) || [];
    matches.push(file.url);
    downloadedByRevision.set(aliasKey, matches);
  }
  let repaired = 0;
  let merged = 0;
  for (const [key, file] of Object.entries({ ...state.files })) {
    if (file.status !== "failed") continue;
    let repairedUrl = repairMalformedUrl(file.url);
    if (!repairedUrl) {
      const matches = downloadedByRevision.get(revisionAliasKey(file.url)) || [];
      if (matches.length === 1) [repairedUrl] = matches;
    }
    if (!repairedUrl || repairedUrl === key) continue;
    const existing = state.files[repairedUrl];
    if (existing) {
      existing.malformedSourceUrls ||= [];
      if (!existing.malformedSourceUrls.includes(file.url)) existing.malformedSourceUrls.push(file.url);
      existing.referrers = [...new Set([...(existing.referrers || []), ...(file.referrers || [])])].slice(0, 20);
      merged += 1;
    } else {
      state.files[repairedUrl] = {
        ...file,
        url: repairedUrl,
        extension: extensionForUrl(repairedUrl),
        format: extensionForUrl(repairedUrl).toUpperCase(),
        status: "pending",
        attempts: 0,
        localPath: null,
        downloadedBytes: null,
        sha256: null,
        contentType: null,
        etag: null,
        lastModified: null,
        error: null,
        repairedAt: new Date().toISOString(),
        malformedSourceUrls: [file.url],
      };
      repaired += 1;
    }
    delete state.files[key];
  }
  saveState(outDirectory, state);
  const summary = writeManifests(outDirectory, state);
  console.log(`Repaired ${repaired} malformed record(s); merged ${merged} duplicate alias(es).`);
  printSummary(summary);
}

async function main(argv = process.argv.slice(2)) {
  const options = parseArgs(argv);
  const command = options._[0];
  if (options.version) {
    console.log(VERSION);
    return;
  }
  if (!command || options.help || command === "help") {
    console.log(usage());
    return;
  }
  if (command === "probe") return probe(options);
  if (command === "inventory") return inventory(options);
  if (command === "download") return download(options);
  if (command === "repair") return repair(options);
  if (command === "report") return report(options);
  throw new Error(`Unknown command: ${command}\n\n${usage()}`);
}

export {
  byteLimitTransform,
  canonicalUrl,
  decodeHtml,
  extensionForUrl,
  extractLinks,
  extractSitemapLocations,
  filePathForUrl,
  formatBytes,
  isFileCandidate,
  parseArgs,
  parseBytes,
  parseRobots,
  repairMalformedUrl,
  robotsAllows,
  safeSegment,
  summarize,
};

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch((error) => {
    console.error(`Error: ${error.message}`);
    process.exitCode = 1;
  });
}
