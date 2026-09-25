# TechTrip-AI-plugins

<p align="center">
  <img src="img/FellowshipOfTheAgents.png" alt="TechTrip-AI-plugins: TechTrip's Claude Code plugins" width="100%" />
</p>

**Everything TechTrip AI releases for Claude Code, in one catalog.** Add the marketplace
once and install what you need. Two kinds of things are listed here: small, focused tools
for working with Claude Code itself, which live in this repository under `plugins/`, and
larger products such as the second brain and the Obsidian knowledge companion, which live
in their own repositories and are listed here so you can find and install them from one
place. Every plugin hosted here ships a `brain-dump` skill: a menu-driven tour that
teaches you how to use it and hands you the exact prompts to type. The tour is always one
command away, so "how did this work again?" three weeks from now is never a search.

## Quick start

Inside Claude Code:

```
/plugin marketplace add TechTripAi/TechTrip-AI-plugins
/plugin install claude-session-finder@TechTrip-AI-plugins
/claude-session-finder:brain-dump
```

The first line registers the marketplace on your machine. The second installs one
plugin at user scope, so it is available in every project. The third starts its tour.
Then, in a new session, ask Claude to "check that the session finder can run on this
machine": the plugin's doctor confirms Python, Claude Code and the session store are in
place and says what to install if not. It never installs anything for you.

## What is in the catalog

| Plugin | What it does | Start here |
|---|---|---|
| [claude-session-finder](plugins/claude-session-finder/) | Find, search and resume past Claude Code sessions across every project on this machine: directory, session id, last active, the last thing you said, and the exact resume command. Flags sessions still running elsewhere so you do not fork them by accident. Hosted in this repository. | `/claude-session-finder:brain-dump` |
| [techtrip-secondbrain](https://github.com/TechTripAi/techtrip-secondbrain) | One-command bootstrapper for a generic LLM Wiki second brain on a fresh Mac: Obsidian, the claude-obsidian companion, a clean vault, the Obsidian MCP server, source-fetch skills (YouTube, X, voice, code, NotebookLM), git sync and backup. Harness-agnostic skills with Claude Code, Cursor and Copilot templates. Own repository. | `/techtrip-secondbrain:brain-dump` |
| [claude-obsidian](https://github.com/TechTripAi/claude-obsidian) | TechTrip AI's maintained fork of [AgriciDaniel's claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) (MIT), a self-organizing AI second brain for Obsidian + Claude Code. Maintained independently with changes that are not merged upstream; original credit and license retained. Installed for you by techtrip-secondbrain, or on its own from here. Own repository. | its README |

Install any of them the same way. This catalog is the only marketplace for all three; the products' repositories no longer carry marketplaces of their own.

```
/plugin install techtrip-secondbrain@TechTrip-AI-plugins
/plugin install claude-obsidian@TechTrip-AI-plugins
```

More will land here as they are built, including packs for education and business. Each
has its own README, CHANGELOG and version.

### Where a plugin lives

- **In this repository, under `plugins/`,** when it is small, Claude Code specific, and
  follows the conventions below. That is the default.
- **In its own repository,** listed here with a `github` source, when it is a product in
  its own right: it has an installer, tests, templates for other harnesses, or deserves
  its own README, issues and release notes. Harness-agnostic skill packs go this way, since
  other harnesses install from the repository, not from this catalog.

## Conventions every plugin hosted here follows

These rules apply to the plugins that live in this repository under `plugins/`. Products
listed from their own repositories carry their own rules, stated in their own READMEs; the
second brain, for example, is an installer by design.


- **A `brain-dump` skill.** Menu-driven, re-runnable, teaches rather than does. Skills
  are namespaced by plugin (`/claude-session-finder:brain-dump`), so every plugin can use
  the same name without conflict.
- **A worker skill that also triggers on plain language.** You can invoke it by name or
  just ask; the description is written so Claude reaches for it when it fits.
- **Standard-library scripts.** Bundled scripts run on the Python or shell that ships
  with macOS. No package installs to use a plugin.
- **Read-only unless the README says otherwise.** A plugin that changes files, settings
  or sessions says so up front and asks before doing it.
- **Advise, never install.** A plugin checks for what it needs and tells you what to
  install for your OS. It does not run installers or package managers on your behalf.
- **Nothing leaves the machine.** Plugins here read local files. Any exception is
  documented in that plugin's README.

## Repository layout

```
.claude-plugin/marketplace.json   the catalog; hosted plugins are "./plugins/<name>", products are github sources
img/                              README images
plugins/<name>/
  .claude-plugin/plugin.json      that plugin's own name, version and metadata
  README.md                       what it does, how to install, how to use
  CHANGELOG.md                    per-plugin release notes
  skills/<skill>/SKILL.md         invoked as /<plugin>:<skill>; scripts and references beside it
```

One repository, many plugins, each versioned on its own. This is the same layout
Anthropic uses for its official plugin marketplace. Products in their own repositories
appear in `marketplace.json` as `{ "source": "github", "repo": "TechTripAi/<name>" }`
entries; the catalog entry's `version` is bumped when that product releases.

## Developing a plugin

Load a plugin for one session without installing it:

```
claude --plugin-dir ./plugins/claude-session-finder
```

Edit, then `/reload-plugins` inside that session to pick up changes. Before a release,
bump `version` in the plugin's `plugin.json`, add a CHANGELOG entry, and update the
matching `version` in `.claude-plugin/marketplace.json`.

Skills in this repo are developed with Anthropic's
[skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator):
draft, run test prompts with and without the skill, review the outputs, iterate. Each
skill keeps its test prompts in `evals/evals.json` so the loop can be rerun.

## Updating

```
/plugin marketplace update TechTrip-AI-plugins
```

then reinstall or `/plugin update` the plugin you use. Auto-update is off for third-party
marketplaces by default.

## License

[FSL-1.1-MIT](LICENSE.md). Functional Source License: free to use, modify and
redistribute for anything except a competing product, and it converts to MIT two years
after each release.

## Credits

Built by [Terry Trippany](https://github.com/TechTripAi) (Try AI Solutions) with Claude
Code. The "Fellowship of the Agents" artwork is TechTrip's.
