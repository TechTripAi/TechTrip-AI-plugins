# Packaging, naming and shipping TechTrip plugins

**Status:** in force
**Last updated:** 2026-11-15
**Owner:** Terry Trippany (Try AI Solutions)

This is the one specification for how a TechTrip AI plugin is packaged, named, presented,
discovered, installed and released. It covers both halves of the question: the architecture
(repositories, plugins, skills, catalog entries) and the presentation (names, descriptions,
READMEs, install wording).

Every other file points here and does not restate it: the catalog `README.md` keeps a short
summary for users, and each repository's `CLAUDE.md` and `AGENTS.md` carry one line that
links to this page. When a rule changes, it changes here first.

## 1. The rules in brief

1. **One catalog.** Users add `TechTripAi/TechTrip-AI-plugins` once and install everything
   from it. No plugin repository is a public marketplace of its own.
2. **One repository per domain.** Engineering, education, knowledge and so on each get one
   repository.
3. **The audience decides the shape.** A domain that only makes sense inside Claude Code may
   hold several small plugins in one repository. A domain that serves other harnesses too is
   one plugin at the repository root, with many skills.
4. **Names go by type and never change after publication.**
5. **Skills are flat and share a prefix.** Every plugin also ships a tour skill, under a
   name of its own.
6. **Unreleased work is private and unlisted, under its final name.** It gets a catalog
   entry when it is ready to ship, and not before.
7. **`plugin.json` is the version of record.** The catalog entry mirrors it.

## 2. Where a plugin lives

| The plugin is | Repository | Layout | Catalog entry |
|---|---|---|---|
| Useful in other harnesses too (Copilot CLI, Cursor, Codex), or has an installer, tests or templates | Its own, `TechTripAi/techtrip-<domain>` | One plugin at the repository root, skills under `skills/` | `{ "source": "github", "repo": "TechTripAi/techtrip-<domain>" }` |
| Small and only meaningful inside Claude Code | `TechTripAi/techtrip-claude-plugins` | `plugins/<name>/`, one directory per plugin | `{ "source": "git-subdir", "url": "TechTripAi/techtrip-claude-plugins", "path": "plugins/<name>" }` |
| A maintained fork | The fork's repository | As upstream | `{ "source": "github", "repo": "TechTripAi/<upstream-name>" }` |

Why the split: GitHub Copilot CLI reads the same `marketplace.json` but cannot follow an
entry that points into a subdirectory. A cross-harness plugin therefore has to sit at the
root of its repository. A plugin in `techtrip-claude-plugins` that later needs another
harness moves to its own repository.

This repository is the catalog only. It holds `marketplace.json`, the README, this `docs/`
folder and the health check. It never holds plugin code.

## 3. Naming

| Thing | Rule | Example |
|---|---|---|
| Product plugin and its repository | `techtrip-<domain>`. Repository name, catalog entry name and manifest name are the same string. | `techtrip-secondbrain`, `techtrip-education` |
| Fork | Keeps the upstream name. | `claude-obsidian` |
| Claude-only tool | Named for what it does. | `claude-sessions` |
| Skill | Lowercase kebab-case. Related skills in one plugin share a prefix. | `study-partner`, `study-quiz` |
| Tour skill | Named by the plugin, in its domain's own word for getting oriented, and carrying the plugin's skill prefix. No two plugins use the same name. | `brain-dump` in `techtrip-secondbrain` |
| Health-check skill, where a plugin has one | `<domain>-doctor`. | `secondbrain-doctor` |
| Catalog `category` | The domain, one word or kebab-case. | `claude-code`, `knowledge`, `engineering`, `education`, `business` |

Further rules:

- **The plugin name names the domain, not a persona and not a maturity level.** A persona
  such as "partner" belongs in a skill name or in a skill's trigger phrases. Words such as
  "beta" or "preview" never go in a name, because a name cannot change later.
- **The `techtrip-` prefix is there because the plugin name travels without the
  organisation.** Users type `/techtrip-secondbrain:brain-dump` and
  `techtrip-secondbrain@TechTrip-AI-plugins`, so the name has to be distinctive alone.
- **A published name never changes.** It is the install id stored in every user's settings.
  Labels change through `displayName`. An unavoidable rename goes through the catalog's
  append-only `renames` map so existing installs migrate.
- **Skills are never grouped into subfolders.** They stay flat under `skills/`; the Agent
  Plugins specification forbids nesting. The shared prefix does the grouping.
- **A tour skill's name is unique across the catalog.** A skill's name is its folder name,
  and a harness that keeps every skill in one folder has no plugin namespace to tell two
  apart, so two plugins with a tour of the same name could not be installed side by side.
  The same holds for every skill of a cross-harness plugin, which is what the shared
  prefix is for.

  | Plugin | Tour skill |
  |---|---|
  | `techtrip-secondbrain` | `brain-dump` |
  | `claude-sessions` | `sessions-briefing` |
  | `techtrip-education` | `study-orientation` |
- **Anything new is lowercase kebab-case.** `TechTrip-AI-plugins` keeps its capitals because
  renaming a marketplace breaks every install.

## 4. From first commit to release

### While it is being built

- The repository is private and carries its final name from the first commit.
- The version stays at `0.x`.
- It is in no catalog. The catalog lists only what a user can install today.
- It is loaded from a checkout, either for one session or as a development marketplace:

  ```
  claude --plugin-dir /path/to/techtrip-<domain>
  ```

  ```
  claude plugin marketplace add /path/to/techtrip-<domain>
  claude plugin install techtrip-<domain>@techtrip-<domain>
  ```

- A skill that is not ready sits in an `incubator/` folder beside `skills/`. Plugin
  manifests read only `skills/`, so an incubator skill never reaches an installed copy.
- A plugin is installed from exactly one place per machine. Never the catalog and a local
  folder for the same plugin, and never a personal `~/.claude/skills` copy of a plugin
  skill. Two copies leave the bare `/name` pointing at whichever loaded first.

### Shipping it

1. The repository's own health check is green.
2. The README, CHANGELOG, license file and tour skill are in place (section 5).
3. The repository is made public.
4. One entry is added to this catalog's `marketplace.json`, with `name`, `source`,
   `description`, `category` and `version`. The catalog's `metadata.version` is bumped
   because an entry was added.
5. A row is added to "What is in the catalog" in the catalog `README.md`.
6. `bash scripts/check.sh` is green in the catalog.

Nothing is renamed at this point. The entry is the only change a user sees.

### Releasing a new version

1. In the plugin's repository: bump `version` in every manifest it ships, add a dated
   CHANGELOG heading, run its health check, commit and push.
2. In this catalog: set the entry's `version` to the same string, run
   `bash scripts/check.sh`, commit and push. The check reads each plugin's live manifest
   from GitHub, so it reports a mismatch until step 1 is pushed.

Claude Code gives users a new copy only when the version goes up, so a change without a
bump does not reach anyone.

## 5. How a plugin presents itself

### Catalog entry

- `description` says what the plugin does for the user in plain words, starting with the
  outcome. It is what people read when browsing `/plugin`, so it stands on its own.
- `category` is the domain (section 3).
- `keywords` are the words someone would search for.
- `author`, `homepage`, `repository` and `license` are filled in on every entry.

### README

- Product and catalog READMEs open with the shared TechTrip banner
  (`img/FellowshipOfTheAgents.png`).
- Then, in this order: one paragraph on what it does, the skills it includes with a prompt
  to try for each, the install block, requirements, and the license.
- The install block is always the catalog route, written the same way everywhere:

  ```
  /plugin marketplace add TechTripAi/TechTrip-AI-plugins
  /plugin install <name>@TechTrip-AI-plugins
  /<name>:<tour skill>
  ```

### Skills

- Every plugin ships a tour skill (section 3): a menu-driven tour that teaches, hands the
  user the exact prompts to type, and never runs anything itself. Its `description` carries
  the word "tour" and the phrase "how do I use", so a user reaches it in plain words
  ("give me the study tour") without knowing its name.
- A worker skill's `description` carries the plain-language phrases a user would say, so the
  agent reaches for the skill without a slash command. It stays within 1024 characters so
  Copilot CLI does not skip it.
- Skills follow the Agent Skills format: `skills/<name>/SKILL.md`, with `name` equal to the
  directory name.

### Promises every plugin keeps

Advise, never install. Read-only and local unless the README says otherwise. Complete,
copyable values. The full list is in the `techtrip-claude-plugins` README.

## 6. Discovery and install, by harness

| Harness | How a user finds it | How a user installs it |
|---|---|---|
| Claude Code | `/plugin`, under TechTrip-AI-plugins; the catalog README table | `/plugin marketplace add TechTripAi/TechTrip-AI-plugins`, then `/plugin install <name>@TechTrip-AI-plugins` |
| GitHub Copilot CLI | The same catalog file | `copilot plugin marketplace add TechTripAi/TechTrip-AI-plugins`, then `copilot plugin install <name>@TechTrip-AI-plugins`. Root-level plugins only. |
| Cursor, Codex, Gemini CLI and anything that reads `SKILL.md` | The plugin's repository | `npx skills add TechTripAi/<repo> -g`. It asks which tools to install for; without `-g` it installs into the current project. `npx skills update -g` picks up releases. |

A README gives this one command as the route for other tools. Linking skill folders from a
clone is for development only and belongs in the README's developing section.

Gemini CLI uses its own authentication, which no TechTrip plugin configures. A plugin's
README tells the user to set up a Gemini API key on a project with billing enabled and
links to Google's instructions without restating them.

Inside a session, a skill is found by its description: the user asks in plain words and the
agent picks the skill. That is why the description rule in section 5 matters.

## 7. Worked examples

### A cross-harness domain: education (shipped)

A study partner is useful outside Claude Code, so it is a product in its own repository.

- **Repository and plugin:** `TechTripAi/techtrip-education`, one plugin at the repository
  root.
- **Skills:** `study-partner`, flat under `skills/`, plus the tour, `study-orientation`.
  Later skills share the `study-` prefix.
- **Catalog entry:** a `github` source pointing at the repository, with `category` set to
  `education`.

  ```json
  {
    "name": "techtrip-education",
    "source": { "source": "github", "repo": "TechTripAi/techtrip-education" },
    "description": "A study partner for certifications, training and any topic you want to learn. ...",
    "version": "0.2.0",
    "category": "education"
  }
  ```

- **Discovery:** the catalog's "What is in the catalog" table, and `/plugin` in Claude Code.
- **Install in Claude Code:** `/plugin install techtrip-education@TechTrip-AI-plugins`,
  then `/techtrip-education:study-orientation`.
- **Install elsewhere:** Copilot CLI installs it from the same catalog. Cursor, Codex
  and Gemini CLI take it with `npx skills add TechTripAi/techtrip-education -g`.

### A cross-harness domain: engineering (in development)

The same pattern, one plugin for the whole domain.

- **Repository and plugin:** `TechTripAi/techtrip-engineering`, one plugin at the repository
  root. Private and unlisted until it is ready to ship.
- **Skills:** flat under `skills/`. The story workflow `story-setup`, `story-plan` and
  `story-implement` share the `story-` prefix; further engineering skills join them over
  time, plus a tour skill.
- **Catalog entry, when it ships:** a `github` source, with `category` set to `engineering`.
- **Install in Claude Code, when it ships:**
  `/plugin install techtrip-engineering@TechTrip-AI-plugins`, then
  its tour skill.

### A Claude-only tool: claude-sessions (shipped)

It reads Claude Code's own session store, so it means nothing in another harness.

- **Repository:** `TechTripAi/techtrip-claude-plugins`, under `plugins/claude-sessions/`.
- **Name:** for what it does, without the `techtrip-` prefix.
- **Catalog entry:** a `git-subdir` source with `path` set to `plugins/claude-sessions`, and
  `category` set to `claude-code`.
- **Install:** `/plugin install claude-sessions@TechTrip-AI-plugins`. Not installable from
  Copilot CLI, by design.

## 8. What this page does not cover

- Which domains are planned, in what order, and any pricing. Those are not public.
- How a particular plugin works inside. That is in the plugin's own repository.
