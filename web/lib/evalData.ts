// Build-time loaders for the eval set and eval results (server only).
//
// Everything here reads files from the repo with Node fs: the eval cases, personas, skills and
// scenarios, plus the results and regression reports written by backend/evals/run.py and
// backend/evals/report.py. Each loader is a `"use cache"` function with cacheLife("max"), so the
// pages are prerendered once at build time (see node_modules/next/dist/docs: Caching). A missing
// or unreadable file never throws: loaders return null or an empty list, and the pages show a
// "not generated yet" state instead.
//
// Results are read from ../results by default. Set FYNN_RESULTS_DIR (absolute, or relative to
// web/) to read them from another directory, for example a copy of fake results during development.

import "server-only";

import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import { cacheLife } from "next/cache";
import { parse as parseYaml } from "yaml";

/* ----------------------------------------------------------------------------------------------
 * Paths
 * -------------------------------------------------------------------------------------------- */

// `next dev` and `next build` run from web/, so the repo root is one level up.
const WEB_DIR = process.cwd();
const REPO_ROOT = path.resolve(WEB_DIR, "..");

const CASES_DIR = path.join(REPO_ROOT, "backend", "evals", "cases");
const SCENARIOS_DIR = path.join(REPO_ROOT, "scenarios");
const PERSONAS_DIR = path.join(REPO_ROOT, "personas");
const SKILLS_DIR = path.join(REPO_ROOT, "skills");
const JUDGE_FILE = path.join(REPO_ROOT, "backend", "evals", "judge.py");
const CONFIG_FILE = path.join(REPO_ROOT, "backend", "fynn", "config.py");

function resultsDir(): string {
  const override = process.env.FYNN_RESULTS_DIR?.trim();
  // The override is a development aid, so keep it out of Turbopack's output file tracing.
  return override ? path.resolve(/*turbopackIgnore: true*/ WEB_DIR, override) : path.join(REPO_ROOT, "results");
}

/* ----------------------------------------------------------------------------------------------
 * Types (normalized from the source files; camelCase throughout)
 * -------------------------------------------------------------------------------------------- */

// Same order as DATASETS in backend/evals/cases.py.
export const DATASETS = ["single_topic", "multi_intent", "context_use", "safety_basic"] as const;
export type Dataset = (typeof DATASETS)[number];

// "unstable" is only ever non-empty when a side ran each case more than once.
export const TRANSITIONS = ["improved", "regressed", "unchanged_pass", "unchanged_fail", "unstable"] as const;
export type Transition = (typeof TRANSITIONS)[number];

export type FactStatus = "PRESENT" | "ABSENT" | "CONTRADICTED";

export interface EvalCase {
  id: string;
  dataset: string;
  persona: string;
  message: string;
  intents: number;
  skills: string[];
  expectedFacts: string[];
  mustNotRegex: string[];
  mustIncludeRegex: string[];
  added: string | null; // YYYY-MM-DD the case joined the set after the first Before vs After run; null if it was in it
}

export interface PersonaInfo {
  id: string;
  name: string;
  summary: string;
}

export interface SkillInfo {
  name: string;
  description: string;
  type: string; // "always_on" | "topic"
  domain: string | null;
}

export interface Scenario {
  id: string;
  title: string;
  kind: string; // "body" | "always_on" | "description"
  skill: string;
  change: string;
  motivation: string;
  hypothesis: { expected: string; detail: string };
  shipped: string | null; // YYYY-MM-DD the edit was copied into skills/
}

// Counts runs: with K runs per case, total is K times the case count and rate the mean pass fraction.
export interface Bucket {
  passed: number;
  total: number;
  rate: number | null;
  errors: number;
}

export interface RunSummary {
  overall: Bucket;
  byDataset: Record<string, Bucket>;
  byIntents: Record<string, Bucket>;
}

export interface Models {
  router: string;
  agent: string;
  judge: string;
}

export interface FactGrade {
  fact: string;
  status: string; // FactStatus, kept open in case the judge schema grows
  note: string;
}

export interface CaseResult {
  id: string;
  dataset: string;
  persona: string;
  intents: number | null;
  message: string;
  skills: string[];
  routed: string[] | null;
  reply: string | null;
  checksPassed: boolean | null;
  checkFailures: string[];
  judgeFacts: FactGrade[];
  judgeReason: string;
  passed: boolean; // with K > 1 runs, the majority outcome; the fields above come from a run with it
  passes: number; // runs passed
  repeats: number; // runs of this case
  errored: number; // runs that errored
  factsPresent: number; // expected facts graded PRESENT, over every judged run
  factsGraded: number; // expected facts graded, over every judged run
  status: string; // "ok" | "error"
  error: string | null;
}

export interface Run {
  name: string;
  bot: string;
  scenario: string | null;
  repeats: number; // runs per case
  skillCap: number | null; // After bot: the most new topic skills per message; null for Before or older files
  createdAt: string;
  models: Models | null;
  selection: { rule: string; caseIds: string[] } | null;
  cases: CaseResult[];
  summary: RunSummary;
}

export interface RunInfo {
  name: string;
  bot: string;
  scenario: string | null;
  createdAt: string;
  models: Models | null;
  repeats: number;
}

export interface RateCell {
  passed: number; // passing runs
  runs: number; // runs (the case count when each case ran once)
  rate: number | null;
}

export interface DatasetComparison {
  total: number;
  baseline: RateCell;
  candidate: RateCell;
  delta: number | null;
}

export interface ReportFailure {
  id: string;
  dataset: string;
  persona: string;
  intents: number | null;
  message: string;
  skills: string[];
  baselineRouting: string[] | null;
  candidateRouting: string[] | null;
  baselineReply: string | null;
  candidateReply: string | null;
  judgeFacts: FactGrade[];
  judgeReason: string;
  checkFailures: string[];
  status: string;
  error: string | null;
  // Runs as the flag rule counted them: errored runs left out unless every run on that side errored.
  baselinePassed: number;
  baselineRuns: number;
  candidatePassed: number;
  candidateRuns: number;
  baselineErrored: number;
  candidateErrored: number;
  baselineAllErrored: boolean;
  candidateAllErrored: boolean;
  baselineError: string | null; // of the baseline run shown
}

export interface FlagRule {
  minFails: number;
  baselineRepeats: number;
  candidateRepeats: number;
  text: string;
}

// One row of the paired test of the net change (backend/evals/stats.py). McNemar rows have the
// flip counts; run-permutation rows the number of cases whose runs disagreed and a descriptive
// persona interval. The other fields are null.
export interface PairedTestRow {
  cases: number;
  meanDiff: number | null;
  improved: number | null;
  regressed: number | null;
  informative: number | null;
  leftOut: number; // pairs left out because one side had only errored runs
  clusters: number | null;
  ciLow: number | null;
  ciHigh: number | null;
  pValue: number | null;
  pHolm: number | null; // per-dataset rows only
  significant: boolean | null; // null when no test ran
}

export interface PairedTest {
  method: string; // "mcnemar_exact" | "run_permutation"
  alpha: number;
  // The persona-cluster bootstrap interval: a description, never a test. Null for McNemar.
  ci: { confidence: number; resamples: number; minClusters: number } | null;
  family: number; // per-dataset p-values in the Holm family
  overall: PairedTestRow;
  byDataset: Record<string, PairedTestRow>;
}

export interface NoiseRow {
  cases: number;
  flips: number | null; // flagged in an A/A run, or expected single-run flips from the baseline's repeats
  regressed: number | null;
  improved: number | null;
}

export interface NoiseFloor {
  source: string; // "aa_run" | "baseline_repeats"
  unit: string; // "flag_rule" | "single_run_flips"
  repeats: number;
  minFails: number | null; // the m the A/A run was flagged with
  sameRule: boolean; // false when the A/A run had a different K than the candidate
  overall: NoiseRow;
  byDataset: Record<string, NoiseRow>;
  unstable: string[];
  unmeasured: string[]; // baseline cases left with fewer than 2 runs once errored runs are taken out
  run: RunInfo | null; // the A/A run, for source "aa_run"
}

export interface Report {
  scenarioId: string | null;
  kind: string; // "change" | "aa"
  baseline: RunInfo;
  candidate: RunInfo;
  selection: { rule: string; caseCount: number };
  overall: { total: number; baseline: RateCell; candidate: RateCell };
  byDataset: Record<string, DatasetComparison>;
  transitions: Record<Transition, string[]>;
  counts: Record<Transition, number>;
  errors: string[];
  failures: ReportFailure[];
  verdict: string; // "Passed" | "Not passed"
  verdictNote: string | null; // when the verdict and the paired test disagree, or for an A/A report
  improvements: ReportFailure[]; // flagged improvements, each with a passing candidate run
  sharpChanges: { dropped: string[]; rose: string[] }; // unstable cases that moved by m of K or more
  baselineErrors: string[];
  factsChanged: string[]; // left out: their graded expected facts differ between the two runs
  // Null in reports written before the statistics layer.
  flagRule: FlagRule | null;
  pairedTest: PairedTest | null;
  noiseFloor: NoiseFloor | null;
  noiseFloorNote: string | null; // why there is no noise floor
  hypothesisResult: { expected: string; observed: string; matches: boolean } | null;
  warnings: string[];
}

/* ----------------------------------------------------------------------------------------------
 * Small parsing helpers (results files are produced by Python; never trust their shape blindly)
 * -------------------------------------------------------------------------------------------- */

type Obj = Record<string, unknown>;

const isObj = (value: unknown): value is Obj => typeof value === "object" && value !== null && !Array.isArray(value);
const str = (value: unknown, fallback = ""): string => (typeof value === "string" ? value : fallback);
const strOrNull = (value: unknown): string | null => (typeof value === "string" ? value : null);
const num = (value: unknown, fallback = 0): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;
const numOrNull = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;
const repeatsOf = (value: unknown): number => Math.max(1, Math.round(num(value, 1)));
const strList = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
const strListOrNull = (value: unknown): string[] | null => (Array.isArray(value) ? strList(value) : null);
const objList = (value: unknown): Obj[] => (Array.isArray(value) ? value.filter(isObj) : []);

function warn(file: string, problem: string) {
  console.warn(`[evalData] ${path.relative(REPO_ROOT, file) || file}: ${problem}`);
}

async function readText(file: string): Promise<string | null> {
  try {
    return await readFile(file, "utf8");
  } catch (error) {
    const code = isObj(error) ? error.code : undefined;
    if (code !== "ENOENT" && code !== "ENOTDIR") warn(file, `could not read (${String(code ?? error)})`);
    return null;
  }
}

async function listDir(dir: string): Promise<string[]> {
  try {
    return (await readdir(dir)).sort();
  } catch {
    return [];
  }
}

/** Parsed JSON, or undefined when the file is missing, unreadable or invalid (the last two are logged). */
async function readJson(file: string): Promise<unknown> {
  const text = await readText(file);
  if (text === null) return undefined;
  try {
    return JSON.parse(text);
  } catch (error) {
    warn(file, `invalid JSON (${error instanceof Error ? error.message : String(error)})`);
    return undefined;
  }
}

async function readYaml(file: string): Promise<unknown> {
  const text = await readText(file);
  if (text === null) return null;
  try {
    return parseYaml(text);
  } catch (error) {
    warn(file, `invalid YAML (${error instanceof Error ? error.message : String(error)})`);
    return null;
  }
}

function toModels(value: unknown): Models | null {
  if (!isObj(value)) return null;
  return { router: str(value.router, "unknown"), agent: str(value.agent, "unknown"), judge: str(value.judge, "unknown") };
}

function toBucket(value: unknown): Bucket {
  const obj = isObj(value) ? value : {};
  return { passed: num(obj.passed), total: num(obj.total), rate: numOrNull(obj.rate), errors: num(obj.errors) };
}

function toBuckets(value: unknown): Record<string, Bucket> {
  if (!isObj(value)) return {};
  return Object.fromEntries(Object.entries(value).map(([key, bucket]) => [key, toBucket(bucket)]));
}

function toFacts(value: unknown): FactGrade[] {
  return objList(value).map((fact) => ({ fact: str(fact.fact), status: str(fact.status, "UNKNOWN"), note: str(fact.note) }));
}

function toCaseResult(value: Obj): CaseResult {
  const routing = isObj(value.routing) ? value.routing : null;
  const checks = isObj(value.checks) ? value.checks : null;
  const judge = isObj(value.judge) ? value.judge : null;
  const runs = objList(value.runs);
  const repeats = runs.length || repeatsOf(value.repeats);
  const passes = runs.length ? runs.filter((run) => run.passed === true).length : value.passed === true ? 1 : 0;
  const errored = runs.length
    ? runs.filter((run) => run.status === "error").length
    : value.status === "error"
      ? 1
      : 0;
  const graded = (runs.length ? runs : [value]).flatMap((run) => (isObj(run.judge) ? objList(run.judge.facts) : []));
  return {
    id: str(value.id),
    dataset: str(value.dataset),
    persona: str(value.persona),
    intents: numOrNull(value.intents),
    message: str(value.message),
    skills: strList(value.skills),
    routed: routing ? [...strList(routing.selected), ...strList(routing.carried)] : null,
    reply: strOrNull(value.reply),
    checksPassed: checks && typeof checks.passed === "boolean" ? checks.passed : null,
    checkFailures: checks ? strList(checks.failures) : [],
    judgeFacts: judge ? toFacts(judge.facts) : [],
    judgeReason: judge ? str(judge.reason) : "",
    passed: value.passed === true,
    passes: num(value.passes, passes),
    repeats,
    errored,
    factsPresent: graded.filter((fact) => fact.status === "PRESENT").length,
    factsGraded: graded.length,
    status: str(value.status, "ok"),
    error: strOrNull(value.error),
  };
}

function toRunInfo(value: unknown): RunInfo {
  const obj = isObj(value) ? value : {};
  return {
    name: str(obj.name),
    bot: str(obj.bot),
    scenario: strOrNull(obj.scenario),
    createdAt: str(obj.created_at),
    models: toModels(obj.models),
    repeats: repeatsOf(obj.repeats),
  };
}

/** `cases` is the fallback run count for reports written before cells had one. */
function toRateCell(value: unknown, cases: number): RateCell {
  const obj = isObj(value) ? value : {};
  return { passed: num(obj.passed), runs: num(obj.runs, cases), rate: numOrNull(obj.rate) };
}

function toFlagRule(value: unknown): FlagRule | null {
  if (!isObj(value)) return null;
  return {
    minFails: num(value.min_fails, 1),
    baselineRepeats: repeatsOf(value.baseline_repeats),
    candidateRepeats: repeatsOf(value.candidate_repeats),
    text: str(value.text),
  };
}

function toTestRow(value: unknown): PairedTestRow {
  const obj = isObj(value) ? value : {};
  return {
    cases: num(obj.cases),
    meanDiff: numOrNull(obj.mean_diff),
    improved: numOrNull(obj.improved),
    regressed: numOrNull(obj.regressed),
    informative: numOrNull(obj.informative),
    leftOut: num(obj.left_out),
    clusters: numOrNull(obj.clusters),
    ciLow: numOrNull(obj.ci_low),
    ciHigh: numOrNull(obj.ci_high),
    pValue: numOrNull(obj.p_value),
    pHolm: numOrNull(obj.p_holm),
    significant: typeof obj.significant === "boolean" ? obj.significant : null,
  };
}

function mapRows<T>(value: unknown, toRow: (row: Obj) => T): Record<string, T> {
  if (!isObj(value)) return {};
  return Object.fromEntries(
    Object.entries(value)
      .filter((entry): entry is [string, Obj] => isObj(entry[1]))
      .map(([key, row]) => [key, toRow(row)]),
  );
}

function toPairedTest(value: unknown): PairedTest | null {
  if (!isObj(value)) return null;
  const ci = isObj(value.ci) ? value.ci : null;
  const byDataset = mapRows(value.by_dataset, toTestRow);
  return {
    method: str(value.method),
    alpha: num(value.alpha, 0.05),
    ci: ci
      ? { confidence: num(ci.confidence, 0.95), resamples: num(ci.resamples), minClusters: num(ci.min_clusters, 3) }
      : null,
    family: num(value.family, Object.values(byDataset).filter((row) => row.pValue !== null).length),
    overall: toTestRow(value.overall),
    byDataset,
  };
}

function toNoiseRow(value: unknown): NoiseRow {
  const obj = isObj(value) ? value : {};
  return {
    cases: num(obj.cases),
    flips: numOrNull(obj.flips),
    regressed: numOrNull(obj.regressed),
    improved: numOrNull(obj.improved),
  };
}

function toNoiseFloor(value: unknown): NoiseFloor | null {
  if (!isObj(value)) return null;
  const source = str(value.source);
  return {
    source,
    unit: str(value.unit, source === "aa_run" ? "flag_rule" : "single_run_flips"),
    repeats: repeatsOf(value.repeats),
    minFails: numOrNull(value.min_fails),
    sameRule: value.same_rule !== false,
    overall: toNoiseRow(value.overall),
    byDataset: mapRows(value.by_dataset, toNoiseRow),
    unstable: strList(value.unstable),
    unmeasured: strList(value.unmeasured),
    run: isObj(value.run) ? toRunInfo(value.run) : null,
  };
}

/* ----------------------------------------------------------------------------------------------
 * Repo content loaders: cases, personas, skills, scenarios
 * -------------------------------------------------------------------------------------------- */

/** All eval cases from backend/evals/cases/<dataset>.yaml, in dataset order. */
export async function getCases(): Promise<EvalCase[]> {
  "use cache";
  cacheLife("max");

  const cases: EvalCase[] = [];
  for (const dataset of DATASETS) {
    const file = path.join(CASES_DIR, `${dataset}.yaml`);
    const raw = await readYaml(file);
    if (raw === null) continue;
    if (!Array.isArray(raw)) {
      warn(file, "expected a YAML list of cases");
      continue;
    }
    for (const item of raw.filter(isObj)) {
      cases.push({
        id: str(item.id),
        dataset: str(item.dataset, dataset),
        persona: str(item.persona),
        message: str(item.message).trim(),
        intents: num(item.intents, 1),
        skills: strList(item.skills),
        expectedFacts: strList(item.expected_facts),
        mustNotRegex: strList(item.must_not_regex),
        mustIncludeRegex: strList(item.must_include_regex),
        added:
          typeof item.added === "string" ? item.added : item.added instanceof Date ? item.added.toISOString().slice(0, 10) : null,
      });
    }
  }
  return cases;
}

/** Persona id, name and one-line summary from personas/*.json, sorted by id. */
export async function getPersonas(): Promise<PersonaInfo[]> {
  "use cache";
  cacheLife("max");

  const personas: PersonaInfo[] = [];
  for (const name of await listDir(PERSONAS_DIR)) {
    if (!name.endsWith(".json")) continue;
    const raw = await readJson(path.join(PERSONAS_DIR, name));
    if (!isObj(raw)) continue;
    personas.push({ id: str(raw.id, name.replace(/\.json$/, "")), name: str(raw.name), summary: str(raw.summary) });
  }
  return personas;
}

const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n/;

/** Frontmatter of skills/*.md (name, description, type, domain), sorted by name. */
export async function getSkills(): Promise<SkillInfo[]> {
  "use cache";
  cacheLife("max");

  const skills: SkillInfo[] = [];
  for (const name of await listDir(SKILLS_DIR)) {
    if (!name.endsWith(".md")) continue;
    const file = path.join(SKILLS_DIR, name);
    const text = await readText(file);
    const match = text?.match(FRONTMATTER);
    if (!match?.[1]) continue;
    let meta: unknown;
    try {
      meta = parseYaml(match[1]);
    } catch {
      warn(file, "invalid frontmatter");
      continue;
    }
    if (!isObj(meta)) continue;
    skills.push({
      name: str(meta.name, name.replace(/\.md$/, "")),
      description: str(meta.description).trim(),
      type: str(meta.type, "topic"),
      domain: strOrNull(meta.domain),
    });
  }
  return skills;
}

/** Skill-edit scenarios from scenarios/<id>/scenario.yaml, sorted by id. */
export async function getScenarios(): Promise<Scenario[]> {
  "use cache";
  cacheLife("max");

  const scenarios: Scenario[] = [];
  for (const id of await listDir(SCENARIOS_DIR)) {
    const raw = await readYaml(path.join(SCENARIOS_DIR, id, "scenario.yaml"));
    if (!isObj(raw)) continue;
    const hypothesis = isObj(raw.hypothesis) ? raw.hypothesis : {};
    scenarios.push({
      id: str(raw.id, id),
      title: str(raw.title, id),
      kind: str(raw.kind),
      skill: str(raw.skill),
      change: str(raw.change).trim(),
      motivation: str(raw.motivation).trim(),
      hypothesis: { expected: str(hypothesis.expected), detail: str(hypothesis.detail).trim() },
      shipped:
        typeof raw.shipped === "string" ? raw.shipped : raw.shipped instanceof Date ? raw.shipped.toISOString().slice(0, 10) : null,
    });
  }
  return scenarios;
}

/** The judge's system prompt, extracted from backend/evals/judge.py (null if it can't be found). */
export async function getJudgeInstructions(): Promise<string | null> {
  "use cache";
  cacheLife("max");

  const source = await readText(JUDGE_FILE);
  const match = source?.match(/JUDGE_SYSTEM = """\\?\r?\n([\s\S]*?)"""/);
  // A backslash at the end of a line inside a Python string joins it with the next line.
  return match?.[1] ? match[1].replace(/\\\r?\n/g, "").trim() : null;
}

/** The After bot's cap on new topic skills per message, from backend/fynn/config.py (null if not found). */
export async function getSkillCap(): Promise<number | null> {
  "use cache";
  cacheLife("max");

  const source = (await readText(CONFIG_FILE)) ?? "";
  const match = source.match(/^MAX_NEW_SKILLS_PER_TURN\s*=\s*(\d+)/m);
  return match?.[1] ? Number(match[1]) : null;
}

/** Default model ids from backend/fynn/config.py, used when no results file names them. */
export async function getConfiguredModels(): Promise<Partial<Models>> {
  "use cache";
  cacheLife("max");

  const source = (await readText(CONFIG_FILE)) ?? "";
  const models: Partial<Models> = {};
  for (const [role, key] of [
    ["router", "ROUTER_MODEL"],
    ["agent", "AGENT_MODEL"],
    ["judge", "JUDGE_MODEL"],
  ] as const) {
    const match = source.match(new RegExp(`^${key}\\s*=\\s*os\\.environ\\.get\\(\\s*"[A-Z_]+"\\s*,\\s*"([^"]+)"`, "m"));
    if (match?.[1]) models[role] = match[1];
  }
  return models;
}

/* ----------------------------------------------------------------------------------------------
 * Results and report loaders
 * -------------------------------------------------------------------------------------------- */

/** A results JSON from backend/evals/run.py, by path relative to the results dir (e.g. "after.json"). */
export async function getRun(relativePath: string): Promise<Run | null> {
  "use cache";
  cacheLife("max");

  const file = path.join(resultsDir(), relativePath);
  const raw = await readJson(file);
  if (raw === undefined) return null;
  if (!isObj(raw) || !Array.isArray(raw.cases) || !isObj(raw.summary)) {
    warn(file, "not a results file (missing cases or summary)");
    return null;
  }
  const selection = isObj(raw.selection) ? raw.selection : null;
  return {
    name: str(raw.name),
    bot: str(raw.bot),
    scenario: strOrNull(raw.scenario),
    repeats: repeatsOf(raw.repeats),
    skillCap: typeof raw.skill_cap === "number" && raw.skill_cap >= 1 ? raw.skill_cap : null,
    createdAt: str(raw.created_at),
    models: toModels(raw.models),
    selection: selection ? { rule: str(selection.rule), caseIds: strList(selection.case_ids) } : null,
    cases: objList(raw.cases).map(toCaseResult),
    summary: {
      overall: toBucket(raw.summary.overall),
      byDataset: toBuckets(raw.summary.by_dataset),
      byIntents: toBuckets(raw.summary.by_intents),
    },
  };
}

/** reports/<name>/report.json from backend/evals/report.py (e.g. "before-vs-after", "s1"). */
export async function getReport(name: string): Promise<Report | null> {
  "use cache";
  cacheLife("max");

  const file = path.join(resultsDir(), "reports", name, "report.json");
  const raw = await readJson(file);
  if (raw === undefined) return null;
  if (!isObj(raw) || !isObj(raw.transitions) || !isObj(raw.pass_rates)) {
    warn(file, "not a report file (missing transitions or pass_rates)");
    return null;
  }
  const transitions = Object.fromEntries(
    TRANSITIONS.map((name) => [name, strList((raw.transitions as Obj)[name])]),
  ) as Record<Transition, string[]>;
  const counts = Object.fromEntries(TRANSITIONS.map((name) => [name, transitions[name].length])) as Record<
    Transition,
    number
  >;
  const rates = raw.pass_rates;
  const overall = isObj(rates.overall) ? rates.overall : {};
  const byDataset = isObj(rates.by_dataset) ? rates.by_dataset : {};
  const selection = isObj(raw.selection) ? raw.selection : {};
  const hypothesis = isObj(raw.hypothesis_result) ? raw.hypothesis_result : null;
  const scenario = isObj(raw.scenario) ? raw.scenario : null;

  const overallTotal = num(overall.total);
  return {
    scenarioId: scenario ? strOrNull(scenario.id) : null,
    kind: str(raw.kind, "change"),
    baseline: toRunInfo(raw.baseline),
    candidate: toRunInfo(raw.candidate),
    selection: { rule: str(selection.rule), caseCount: num(selection.case_count) },
    overall: {
      total: overallTotal,
      baseline: toRateCell(overall.baseline, overallTotal),
      candidate: toRateCell(overall.candidate, overallTotal),
    },
    byDataset: mapRows(byDataset, (row) => ({
      total: num(row.total),
      baseline: toRateCell(row.baseline, num(row.total)),
      candidate: toRateCell(row.candidate, num(row.total)),
      delta: numOrNull(row.delta),
    })),
    transitions,
    counts,
    errors: strList(raw.errors),
    failures: objList(raw.failures).map(toReportFailure),
    improvements: objList(raw.improvements).map(toReportFailure),
    sharpChanges: {
      dropped: isObj(raw.sharp_changes) ? strList(raw.sharp_changes.dropped) : [],
      rose: isObj(raw.sharp_changes) ? strList(raw.sharp_changes.rose) : [],
    },
    baselineErrors: strList(raw.baseline_errors),
    factsChanged: strList(raw.facts_changed),
    verdict: str(raw.verdict),
    verdictNote: strOrNull(raw.verdict_note),
    flagRule: toFlagRule(raw.flag_rule),
    pairedTest: toPairedTest(raw.paired_test),
    noiseFloor: toNoiseFloor(raw.noise_floor),
    noiseFloorNote: strOrNull(raw.noise_floor_note),
    hypothesisResult: hypothesis
      ? { expected: str(hypothesis.expected), observed: str(hypothesis.observed), matches: hypothesis.matches === true }
      : null,
    warnings: strList(raw.warnings),
  };
}

function toReportFailure(failure: Obj): ReportFailure {
  return {
    id: str(failure.id),
    dataset: str(failure.dataset),
    persona: str(failure.persona),
    intents: numOrNull(failure.intents),
    message: str(failure.message),
    skills: strList(failure.skills),
    baselineRouting: strListOrNull(failure.baseline_routing),
    candidateRouting: strListOrNull(failure.candidate_routing),
    baselineReply: strOrNull(failure.baseline_reply),
    candidateReply: strOrNull(failure.candidate_reply),
    judgeFacts: toFacts(failure.judge_facts),
    judgeReason: str(failure.judge_reason),
    checkFailures: strList(failure.check_failures),
    status: str(failure.status, "ok"),
    error: strOrNull(failure.error),
    baselinePassed: num(failure.baseline_passed, 1),
    baselineRuns: repeatsOf(failure.baseline_runs),
    candidatePassed: num(failure.candidate_passed, 0),
    candidateRuns: repeatsOf(failure.candidate_runs),
    baselineErrored: num(failure.baseline_errored),
    candidateErrored: num(failure.candidate_errored),
    baselineAllErrored: failure.baseline_all_errored === true,
    candidateAllErrored: failure.candidate_all_errored === true,
    baselineError: strOrNull(failure.baseline_error),
  };
}

/* ----------------------------------------------------------------------------------------------
 * Page view models
 * -------------------------------------------------------------------------------------------- */

export interface RunMeta {
  file: string; // path relative to the results dir
  name: string;
  bot: string;
  scenario: string | null;
  createdAt: string;
  models: Models | null;
  repeats: number;
  cases: number;
  total: number; // runs
  passed: number; // passing runs
  rate: number | null;
  errors: number;
  selectionRule: string | null;
}

export interface CaseSide {
  routed: string[] | null;
  reply: string | null;
  passed: boolean | null; // of the run shown
  passes: number | null; // runs passed, out of `runs`
  runs: number;
  errored: number; // runs that errored, left out of `runs` unless `allErrored`
  allErrored: boolean;
  judgeReason: string;
  notPresent: FactGrade[]; // facts the judge did not grade PRESENT
  checkFailures: string[];
  error: string | null;
}

export interface CaseChange {
  id: string;
  dataset: string;
  persona: string;
  intents: number | null;
  message: string;
  skills: string[];
  transition: "improved" | "regressed" | "unstable";
  sharp: "dropped" | "rose" | null; // an unstable case that moved by at least m of K runs
  baseline: CaseSide | null;
  candidate: CaseSide | null;
}

export interface Comparison {
  report: Omit<Report, "failures" | "improvements">;
  regressed: CaseChange[];
  improved: CaseChange[];
  unstable: CaseChange[];
  baselineCases: number | null; // cases in the baseline run the report compared against, when that file is found
  // Why some case details may be partial (e.g. a results file newer than the report).
  notes: string[];
}

export interface ScenarioResult {
  scenario: Scenario;
  run: RunMeta | null;
  comparison: Comparison | null;
}

export interface ResultsData {
  before: { meta: RunMeta; summary: RunSummary } | null;
  after: { meta: RunMeta; summary: RunSummary } | null;
  beforeVsAfter: Comparison | null;
  scenarios: ScenarioResult[];
  runs: RunMeta[];
  caseCount: number;
  hasAnyResults: boolean;
}

function runMeta(file: string, run: Run): RunMeta {
  return {
    file,
    name: run.name,
    bot: run.bot,
    scenario: run.scenario,
    createdAt: run.createdAt,
    models: run.models,
    repeats: run.repeats,
    cases: run.cases.length,
    total: run.summary.overall.total,
    passed: run.summary.overall.passed,
    rate: run.summary.overall.rate,
    errors: run.summary.overall.errors,
    selectionRule: run.selection?.rule ?? null,
  };
}

// run.py names a run after its --out file: scenario runs live in scenarios/<id>.json.
function runFileFor(info: RunInfo): string | null {
  if (info.scenario) return `scenarios/${info.scenario}.json`;
  return info.name ? `${info.name}.json` : null;
}

function side(result: CaseResult): CaseSide {
  return {
    routed: result.routed,
    reply: result.reply,
    passed: result.passed,
    passes: result.passes,
    runs: result.repeats,
    errored: result.errored,
    allErrored: result.errored > 0 && result.errored === result.repeats,
    judgeReason: result.judgeReason,
    notPresent: result.judgeFacts.filter((fact) => fact.status !== "PRESENT"),
    checkFailures: result.checkFailures,
    error: result.error,
  };
}

/** Earlier results files kept in results/archive/ after a newer run replaced them, while a report still compares them. */
const ARCHIVE_DIR = "archive";

async function archivedRun(info: RunInfo): Promise<Run | null> {
  for (const name of await listDir(path.join(resultsDir(), ARCHIVE_DIR))) {
    if (!name.endsWith(".json")) continue;
    const run = await getRun(path.join(ARCHIVE_DIR, name));
    if (run && run.name === info.name && run.scenario === info.scenario && run.createdAt === info.createdAt) return run;
  }
  return null;
}

async function matchingRun(info: RunInfo, label: string, notes: string[]): Promise<Run | null> {
  const file = runFileFor(info);
  if (!file) return null;
  const run = await getRun(file);
  if (run?.createdAt !== info.createdAt) {
    const archived = await archivedRun(info);
    if (archived) return archived;
  }
  if (!run) {
    notes.push(`The ${label} results file (${file}) is missing, so some case details are partial.`);
    return null;
  }
  if (run.createdAt !== info.createdAt) {
    notes.push(
      `The ${label} results file (${file}) is from a different run than this report, so case details come from the report only.`,
    );
    return null;
  }
  return run;
}

async function buildComparison(report: Report, cases: EvalCase[]): Promise<Comparison> {
  const notes: string[] = [];
  const baselineRun = await matchingRun(report.baseline, "baseline", notes);
  const candidateRun = await matchingRun(report.candidate, "candidate", notes);
  const { failures, improvements, ...rest } = report;
  const baseById = new Map<string, CaseResult>((baselineRun?.cases ?? []).map((c) => [c.id, c]));
  const candById = new Map<string, CaseResult>((candidateRun?.cases ?? []).map((c) => [c.id, c]));
  const detailById = new Map<string, ReportFailure>([...failures, ...improvements].map((f) => [f.id, f]));
  const caseById = new Map<string, EvalCase>(cases.map((c) => [c.id, c]));
  const dropped = new Set(report.sharpChanges.dropped);
  const rose = new Set(report.sharpChanges.rose);

  const change = (id: string, transition: CaseChange["transition"]): CaseChange => {
    const failure = transition === "unstable" ? undefined : detailById.get(id);
    // A flagged case should show runs with the flagged outcomes: for a regression a passing baseline
    // run and a failing candidate run, for an improvement the other way round. The results files
    // keep each side's majority run, which a lenient flag rule or errored runs can leave on the other
    // side; the report's entry always holds runs with the flagged outcomes.
    const flaggedPass = transition === "improved";
    const baseMajority = baseById.get(id);
    const candMajority = candById.get(id);
    const base =
      failure && baseMajority && (baseMajority.passed === flaggedPass || baseMajority.status === "error")
        ? undefined
        : baseMajority;
    const cand =
      failure && candMajority && (candMajority.passed !== flaggedPass || candMajority.status === "error")
        ? undefined
        : candMajority;
    // A flagged case shows the run counts the flag rule used, from the report entry, on both sides.
    const counted = (sideFrom: CaseSide, which: "baseline" | "candidate"): CaseSide => {
      if (!failure) return sideFrom;
      return which === "baseline"
        ? {
            ...sideFrom,
            passes: failure.baselinePassed,
            runs: failure.baselineRuns,
            errored: failure.baselineErrored,
            allErrored: failure.baselineAllErrored,
          }
        : {
            ...sideFrom,
            passes: failure.candidatePassed,
            runs: failure.candidateRuns,
            errored: failure.candidateErrored,
            allErrored: failure.candidateAllErrored,
          };
    };
    const source = cand ?? base;
    const evalCase = caseById.get(id);
    return {
      id,
      dataset: source?.dataset ?? failure?.dataset ?? evalCase?.dataset ?? "",
      persona: source?.persona ?? failure?.persona ?? evalCase?.persona ?? "",
      intents: source?.intents ?? failure?.intents ?? evalCase?.intents ?? null,
      message: source?.message ?? failure?.message ?? evalCase?.message ?? "",
      skills: source?.skills ?? failure?.skills ?? evalCase?.skills ?? [],
      transition,
      sharp: dropped.has(id) ? "dropped" : rose.has(id) ? "rose" : null,
      baseline: base
        ? counted(side(base), "baseline")
        : failure
          ? {
              routed: failure.baselineRouting,
              reply: failure.baselineReply,
              passed: !flaggedPass,
              passes: failure.baselinePassed,
              runs: failure.baselineRuns,
              errored: failure.baselineErrored,
              allErrored: failure.baselineAllErrored,
              judgeReason: "",
              notPresent: [],
              checkFailures: [],
              error: failure.baselineError,
            }
          : null,
      candidate: cand
        ? counted(side(cand), "candidate")
        : failure
          ? {
              routed: failure.candidateRouting,
              reply: failure.candidateReply,
              passed: flaggedPass,
              passes: failure.candidatePassed,
              runs: failure.candidateRuns,
              errored: failure.candidateErrored,
              allErrored: failure.candidateAllErrored,
              judgeReason: flaggedPass ? "" : failure.judgeReason,
              notPresent: flaggedPass ? [] : failure.judgeFacts.filter((fact) => fact.status !== "PRESENT"),
              checkFailures: failure.checkFailures,
              error: failure.error,
            }
          : null,
    };
  };

  return {
    report: rest,
    regressed: report.transitions.regressed.map((id) => change(id, "regressed")),
    improved: report.transitions.improved.map((id) => change(id, "improved")),
    unstable: report.transitions.unstable.map((id) => change(id, "unstable")),
    baselineCases: baselineRun?.cases.length ?? null,
    notes,
  };
}

/** Everything the /results page shows. */
export async function getResultsData(): Promise<ResultsData> {
  "use cache";
  cacheLife("max");

  const [cases, scenarios, before, after, beforeVsAfterReport] = await Promise.all([
    getCases(),
    getScenarios(),
    getRun("before.json"),
    getRun("after.json"),
    getReport("before-vs-after"),
  ]);

  const runs: RunMeta[] = [];
  if (before) runs.push(runMeta("before.json", before));
  if (after) runs.push(runMeta("after.json", after));

  const scenarioResults: ScenarioResult[] = [];
  for (const scenario of scenarios) {
    const file = `scenarios/${scenario.id}.json`;
    const [run, report] = await Promise.all([getRun(file), getReport(scenario.id)]);
    const meta = run ? runMeta(file, run) : null;
    if (meta) runs.push(meta);
    scenarioResults.push({ scenario, run: meta, comparison: report ? await buildComparison(report, cases) : null });
  }

  const beforeVsAfter = beforeVsAfterReport ? await buildComparison(beforeVsAfterReport, cases) : null;
  return {
    before: before ? { meta: runMeta("before.json", before), summary: before.summary } : null,
    after: after ? { meta: runMeta("after.json", after), summary: after.summary } : null,
    beforeVsAfter,
    scenarios: scenarioResults,
    runs,
    caseCount: cases.length,
    hasAnyResults: runs.length > 0 || beforeVsAfter !== null || scenarioResults.some((s) => s.comparison !== null),
  };
}

export interface FrameworkData {
  repeats: { before: number | null; after: number | null }; // runs per case in the latest full runs
  cases: EvalCase[];
  personas: PersonaInfo[];
  skills: SkillInfo[];
  scenarios: Scenario[];
  judgeInstructions: string | null;
  judgeModel: { model: string; source: "results" | "config" } | null;
}

/** Everything the /framework page shows. */
export async function getFrameworkData(): Promise<FrameworkData> {
  "use cache";
  cacheLife("max");

  const [cases, personas, skills, scenarios, judgeInstructions, configured, after, before] = await Promise.all([
    getCases(),
    getPersonas(),
    getSkills(),
    getScenarios(),
    getJudgeInstructions(),
    getConfiguredModels(),
    getRun("after.json"),
    getRun("before.json"),
  ]);
  const fromResults = after?.models?.judge ?? before?.models?.judge;
  const judgeModel = fromResults
    ? { model: fromResults, source: "results" as const }
    : configured.judge
      ? { model: configured.judge, source: "config" as const }
      : null;
  const repeats = { before: before?.repeats ?? null, after: after?.repeats ?? null };
  return { repeats, cases, personas, skills, scenarios, judgeInstructions, judgeModel };
}

/* ----------------------------------------------------------------------------------------------
 * Before vs After: where the two designs can differ
 * -------------------------------------------------------------------------------------------- */

export interface GroupStat {
  cases: number;
  passed: number; // passing runs
  runs: number;
  rate: number | null; // passing runs over runs
  factsPresent: number;
  factsGraded: number;
}

export interface CaseGroup {
  key: string;
  label: string;
  note: string;
  before: GroupStat | null;
  after: GroupStat | null;
}

export interface BeforeAfterData {
  before: { meta: RunMeta; run: Run } | null;
  after: { meta: RunMeta; run: Run } | null;
  comparison: Comparison | null;
  overall: CaseGroup | null;
  byDomains: CaseGroup[]; // cases whose labeled skills need one Before domain vs more than one
  crossByQuestions: CaseGroup[]; // the cases that need a second domain, split by number of questions
  byQuestions: CaseGroup[];
  byDataset: CaseGroup[];
  byOrigin: CaseGroup[]; // the cases of the first Before vs After run, then each later batch by date added
  crossDomain: { ids: string[]; domains: Record<string, string[]> }; // case id -> Before domains it spans
  pending: string[]; // cases in the eval set that the committed results do not cover yet
  caseCount: number;
}

function groupStat(run: Run | null, ids: Set<string>): GroupStat | null {
  if (!run) return null;
  const cases = run.cases.filter((c) => ids.has(c.id));
  const passed = cases.reduce((sum, c) => sum + c.passes, 0);
  const runs = cases.reduce((sum, c) => sum + c.repeats, 0);
  return {
    cases: cases.length,
    passed,
    runs,
    rate: runs ? passed / runs : null,
    factsPresent: cases.reduce((sum, c) => sum + c.factsPresent, 0),
    factsGraded: cases.reduce((sum, c) => sum + c.factsGraded, 0),
  };
}

/** Before domains a case's labeled topic skills fall in. Only cases spanning two or more need a second domain expert. */
export function caseDomains(evalCase: EvalCase, skillDomain: Map<string, string>): string[] {
  return [...new Set(evalCase.skills.map((skill) => skillDomain.get(skill)).filter((d): d is string => Boolean(d)))].sort();
}

/** Everything the Before vs After pages show. */
export async function getBeforeAfterData(): Promise<BeforeAfterData> {
  "use cache";
  cacheLife("max");

  const [cases, skills, before, after, report] = await Promise.all([
    getCases(),
    getSkills(),
    getRun("before.json"),
    getRun("after.json"),
    getReport("before-vs-after"),
  ]);
  const skillDomain = new Map(skills.flatMap((s) => (s.type === "topic" && s.domain ? [[s.name, s.domain] as const] : [])));
  const domains = Object.fromEntries(cases.map((c) => [c.id, caseDomains(c, skillDomain)]));
  const crossIds = cases.filter((c) => (domains[c.id]?.length ?? 0) > 1).map((c) => c.id);
  const cross = new Set(crossIds);

  const group = (key: string, label: string, note: string, ids: string[]): CaseGroup => {
    const set = new Set(ids);
    return { key, label, note, before: groupStat(before, set), after: groupStat(after, set) };
  };
  const questions = (n: number) => (n === 1 ? "1 question" : `${n} questions`);
  const hasCases = (g: CaseGroup) => (g.after?.cases ?? g.before?.cases ?? 0) > 0;
  const byQuestions = [1, 2, 3]
    .map((n) => group(`q${n}`, questions(n), "", cases.filter((c) => c.intents === n).map((c) => c.id)))
    .filter(hasCases);
  const crossByQuestions = [1, 2, 3]
    .map((n) =>
      group(`cross-q${n}`, questions(n), "", cases.filter((c) => cross.has(c.id) && c.intents === n).map((c) => c.id)),
    )
    .filter(hasCases);
  const byDataset = DATASETS.map((d) => group(d, d, "", cases.filter((c) => c.dataset === d).map((c) => c.id))).filter(
    (g) => (g.after?.cases ?? g.before?.cases ?? 0) > 0,
  );
  const addedDates = [...new Set(cases.flatMap((c) => (c.added ? [c.added] : [])))].sort();
  const byOrigin = addedDates.length
    ? [
        group("original", "In the first run", "", cases.filter((c) => !c.added).map((c) => c.id)),
        ...addedDates.map((d) => {
          const ids = cases.filter((c) => c.added === d).map((c) => c.id);
          const needSecond = ids.filter((id) => cross.has(id)).length;
          const note = needSecond === ids.length ? "each needs a second domain" : `${needSecond} of ${ids.length} need a second domain`;
          return group(`added-${d}`, `Added ${d}`, note, ids);
        }),
      ].filter(hasCases)
    : [];

  return {
    before: before ? { meta: runMeta("before.json", before), run: before } : null,
    after: after ? { meta: runMeta("after.json", after), run: after } : null,
    comparison: report ? await buildComparison(report, cases) : null,
    overall: cases.length ? group("all", "All cases", "", cases.map((c) => c.id)) : null,
    byDomains: [
      group(
        "cross",
        "Needs a second domain",
        "skills span 2+ Before domains; a Before agent lacks some",
        crossIds,
      ),
      group(
        "single",
        "One domain is enough",
        "Before holds every labeled skill and more; After loads a subset",
        cases.filter((c) => !cross.has(c.id)).map((c) => c.id),
      ),
    ],
    crossByQuestions,
    byQuestions,
    byDataset,
    byOrigin,
    crossDomain: { ids: crossIds, domains },
    pending: cases
      .map((c) => c.id)
      .filter((id) => [before, after].some((run) => run && !run.cases.some((c) => c.id === id))),
    caseCount: cases.length,
  };
}

/* ----------------------------------------------------------------------------------------------
 * Skill cap: the After bot with a higher cap on new skills per message
 * -------------------------------------------------------------------------------------------- */

/** The cap-4 After run (run.py --max-skills 4 --out results/cap4.json) and its report (reports/cap4). */
export const CAP_RUN = { file: "cap4.json", report: "cap4" } as const;

// After runs written before results recorded skill_cap all used 3 (LEGACY_SKILL_CAP in backend/evals/stats.py).
const LEGACY_SKILL_CAP = 3;

export interface CapCaseSide {
  passed: boolean;
  loaded: number; // topic skills the router picked
  missing: string[]; // labeled skills it did not pick
}

export interface CapCase {
  id: string;
  message: string;
  skills: string[];
  baseline: CapCaseSide | null;
  candidate: CapCaseSide | null;
}

export interface CapData {
  baselineCap: number | null;
  cap: number | null;
  comparison: Comparison | null;
  overCap: CapCase[]; // cases labeled with more topic skills than the baseline's cap
}

function capSide(run: Run | null, evalCase: EvalCase): CapCaseSide | null {
  const result = run?.cases.find((c) => c.id === evalCase.id);
  if (!result || result.status === "error") return null;
  const routed = result.routed ?? [];
  return { passed: result.passed, loaded: routed.length, missing: evalCase.skills.filter((s) => !routed.includes(s)) };
}

/** Everything the skill-cap section shows. The baseline cap comes from after.json, or from config.py for older files. */
export async function getCapData(): Promise<CapData> {
  "use cache";
  cacheLife("max");

  const [cases, after, capRun, report, configured] = await Promise.all([
    getCases(),
    getRun("after.json"),
    getRun(CAP_RUN.file),
    getReport(CAP_RUN.report),
    getSkillCap(),
  ]);
  const baselineCap = after ? (after.skillCap ?? LEGACY_SKILL_CAP) : configured;
  const overCap = baselineCap === null ? [] : cases.filter((c) => c.skills.length > baselineCap);
  return {
    baselineCap,
    cap: capRun?.skillCap ?? null,
    comparison: report ? await buildComparison(report, cases) : null,
    overCap: overCap.map((c) => ({
      id: c.id,
      message: c.message,
      skills: c.skills,
      baseline: capSide(after, c),
      candidate: capSide(capRun, c),
    })),
  };
}
