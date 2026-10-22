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

export const TRANSITIONS = ["improved", "regressed", "unchanged_pass", "unchanged_fail"] as const;
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
}

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
  passed: boolean;
  status: string; // "ok" | "error"
  error: string | null;
}

export interface Run {
  name: string;
  bot: string;
  scenario: string | null;
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
}

export interface RateCell {
  passed: number;
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
}

export interface Report {
  scenarioId: string | null;
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
  };
}

function toRateCell(value: unknown): RateCell {
  const obj = isObj(value) ? value : {};
  return { passed: num(obj.passed), rate: numOrNull(obj.rate) };
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

  return {
    scenarioId: scenario ? strOrNull(scenario.id) : null,
    baseline: toRunInfo(raw.baseline),
    candidate: toRunInfo(raw.candidate),
    selection: { rule: str(selection.rule), caseCount: num(selection.case_count) },
    overall: { total: num(overall.total), baseline: toRateCell(overall.baseline), candidate: toRateCell(overall.candidate) },
    byDataset: Object.fromEntries(
      Object.entries(byDataset)
        .filter((entry): entry is [string, Obj] => isObj(entry[1]))
        .map(([dataset, row]) => [
          dataset,
          {
            total: num(row.total),
            baseline: toRateCell(row.baseline),
            candidate: toRateCell(row.candidate),
            delta: numOrNull(row.delta),
          },
        ]),
    ),
    transitions,
    counts,
    errors: strList(raw.errors),
    failures: objList(raw.failures).map((failure) => ({
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
    })),
    verdict: str(raw.verdict),
    hypothesisResult: hypothesis
      ? { expected: str(hypothesis.expected), observed: str(hypothesis.observed), matches: hypothesis.matches === true }
      : null,
    warnings: strList(raw.warnings),
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
  total: number;
  passed: number;
  rate: number | null;
  errors: number;
  selectionRule: string | null;
}

export interface CaseSide {
  routed: string[] | null;
  reply: string | null;
  passed: boolean | null;
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
  transition: "improved" | "regressed";
  baseline: CaseSide | null;
  candidate: CaseSide | null;
}

export interface Comparison {
  report: Omit<Report, "failures">;
  regressed: CaseChange[];
  improved: CaseChange[];
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
    judgeReason: result.judgeReason,
    notPresent: result.judgeFacts.filter((fact) => fact.status !== "PRESENT"),
    checkFailures: result.checkFailures,
    error: result.error,
  };
}

async function matchingRun(info: RunInfo, label: string, notes: string[]): Promise<Run | null> {
  const file = runFileFor(info);
  if (!file) return null;
  const run = await getRun(file);
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
  const { failures, ...rest } = report;
  const baseById = new Map<string, CaseResult>((baselineRun?.cases ?? []).map((c) => [c.id, c]));
  const candById = new Map<string, CaseResult>((candidateRun?.cases ?? []).map((c) => [c.id, c]));
  const failureById = new Map<string, ReportFailure>(failures.map((f) => [f.id, f]));
  const caseById = new Map<string, EvalCase>(cases.map((c) => [c.id, c]));

  const change = (id: string, transition: CaseChange["transition"]): CaseChange => {
    const base = baseById.get(id);
    const cand = candById.get(id);
    const failure = failureById.get(id);
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
      baseline: base
        ? side(base)
        : failure
          ? {
              routed: failure.baselineRouting,
              reply: failure.baselineReply,
              passed: true,
              judgeReason: "",
              notPresent: [],
              checkFailures: [],
              error: null,
            }
          : null,
      candidate: cand
        ? side(cand)
        : failure
          ? {
              routed: failure.candidateRouting,
              reply: failure.candidateReply,
              passed: false,
              judgeReason: failure.judgeReason,
              notPresent: failure.judgeFacts.filter((fact) => fact.status !== "PRESENT"),
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
  return { cases, personas, skills, scenarios, judgeInstructions, judgeModel };
}
