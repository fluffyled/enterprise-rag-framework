# Agent instructions

## CodeGraph first

When this repository has a `.codegraph/` directory, use CodeGraph before text searches or file reads to understand or locate code, and before editing code.

Prefer the `codegraph_explore` MCP tool with `projectPath` set to this repository. Query the relevant files, symbols, and call paths. Treat returned verbatim source as already read. If MCP is unavailable, use `codegraph explore` from the repository directory.

If no `.codegraph/` directory exists, use ordinary tools. Do not initialize an index automatically; indexing is the user's decision.

## Ponytail

Use the available Ponytail skill for coding tasks, in full mode unless the user changes it. Prefer existing code, standard libraries, and the smallest correct change. Preserve required validation, error handling, security, and appropriate verification.

## Disk policy

The owner requires all project downloads, model weights, environments, caches and temporary files on D:, never C:. Before running shell tools or package installers, dot-source `D:\хакатон\project-env.ps1`. Python entry points must configure `answering` before third-party model libraries. Do not move existing Python, VS Code, Windows drivers, or Codex data without establishing that this task installed them. Never clear unrelated caches or user files.
