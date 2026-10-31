# Firmware-Alchemist — Third Party Notices

This project integrates with the following open-source repositories.

---

## 1. AI.duino

**Repository:** https://github.com/NikolaiRadke/AI.duino  
**License:** Apache License 2.0  
**Copyright:** 2025 Monster Maker  

**Files used from this repository:**
- `AI.duino/aiduino/extension/out/utils/codeAnalyzer.js`
  - Vendored to: `vendor/aiduino/codeAnalyzer.js`
  - Ported to Python in: `integrations/aiduino/__init__.py`
  - Functions integrated: `extractPinConfiguration`, `extractPortManipulation`,
    `extractLibraries`, `extractGlobalVariables`
  - Blocking delay analysis pattern ported from the agentic optimization workflow.

**Attribution required by Apache 2.0:**
```
Copyright 2025 Monster Maker

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
```

---

## 2. Arduino-Copilot

**Repository:** https://github.com/JibinES/Arduino-Copilot  
**License:** MIT (per package.json)  
**Author:** JibinES  

**Files used from this repository:**
- `Arduino-Copilot/src/arduino/pin-analyzer.ts`
  - Vendored to: `vendor/arduino_copilot/pin-analyzer.ts`
  - Exposed via Node.js sidecar: `integrations/arduino_copilot/sidecar.js`
  - Python adapter: `integrations/arduino_copilot/__init__.py`
  - Functions: `analyzePins`, `formatPinAnalysis`

- `Arduino-Copilot/src/arduino/error-parser.ts`
  - Vendored to: `vendor/arduino_copilot/error-parser.ts`
  - Exposed via sidecar: `integrations/arduino_copilot/sidecar.js`
  - Functions: `parseGccErrors`, `parseMemoryUsage`, `formatMemoryAdvice`

- `Arduino-Copilot/src/arduino/cli.ts`
  - Vendored to: `vendor/arduino_copilot/cli.ts` (reference)
  - Compilation logic adapted in: `integrations/tiesta/__init__.py`

**MIT License:**
```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 3. Cyréna

**Repository:** https://github.com/Christo262/Cyrena_App  
**License:** MIT (per repository)  
**Author:** Christo262  

**Architecture patterns integrated:**
- `IPromptManager` interface from `Cyrena.Core/Contracts/IPromptManager.cs`
  - Ported to Python: `integrations/cyrena/__init__.py :: PromptManager`
- `Prompt` model from `Cyrena.Core/Models/Prompt.cs`
  - Ported to Python: `integrations/cyrena/__init__.py :: CyrenaPrompt`
- Project-structure awareness (Arduino/PlatformIO detection)
  - Implemented in: `integrations/cyrena/__init__.py :: ProjectContextLoader`

Note: Cyréna's .NET runtime cannot be embedded. The IPromptManager pattern
and project-structure detection logic are faithfully ported to Python.

---

## 4. Tiesta

**Repository:** https://pypi.org/project/tiesta/  
**License:** MIT  
**Version:** 0.2.0  

**Integration method:** Installed as a pip package (`tiesta==0.2.0`).

**Classes imported directly:**
- `tiesta.core.orchestrator.Orchestrator` — agentic execution loop
- `tiesta.core.orchestrator.OrchestratorConfig` — max_turns, max_correction_attempts
- `tiesta.core.orchestrator.ToolRegistry` — tool registration
- `tiesta.core.llm_client.LLMClient` — Ollama client
- `tiesta.tools.hardware_ops.HardwareOpsTool` — serial port scanning

**Adapter:** `integrations/tiesta/__init__.py`

---

## Wokwi

Wokwi is not redistributed in this project. Firmware-Alchemist generates
Wokwi-compatible project files (`diagram.json`, `wokwi.toml`) that are opened
in the official Wokwi simulator. Wokwi's own terms of service apply when using
the simulator.

- Wokwi diagram format: https://docs.wokwi.com/diagram-format
- Wokwi for VS Code: https://marketplace.visualstudio.com/items?itemName=wokwi.wokwi-vscode

---

## Gemma 4

Gemma 4 is accessed via local Ollama inference. Gemma is governed by Google's
Gemma Terms of Use (https://ai.google.dev/gemma/terms). No Gemma weights are
redistributed in this project.

