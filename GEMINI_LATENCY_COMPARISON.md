# NexusAI Phase 3 — Gemini Latency Comparison (Streaming vs Non-Streaming)

**Date**: September 21, 2026  
**Active Model**: `gemini-3.5-flash-lite`  
**Candidate Chain**: `['gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3-flash-preview', 'gemini-3.1-flash-lite']`  
**Iterations Per Test Case**: `3 iterations each`  

---

## 1. Executive Summary Table

| Category | Question | Prompt Chars (Tokens) | Context Chars | Non-Streaming Total (Avg) | Streaming TTFT (Avg) | Streaming Total (Avg) | Perceived Gain (TTFT) |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Simple Factual** | What is the heliosphere?... | 4611 (1213) | 3428 | **5998.1 ms** | **2136.2 ms** | 2722.9 ms | **3861.9 ms (2.8x faster)** |
| **Conceptual** | Explain the zero-trust security architec... | 1519 (400) | 269 | **902.5 ms** | **1163.1 ms** | 1178.5 ms | **-260.5 ms (0.8x faster)** |
| **Comparison** | What is the difference between gas giant... | 6380 (1679) | 5164 | **2643.6 ms** | **13157.0 ms** | 13594.6 ms | **-10513.5 ms (0.2x faster)** |
| **Multi-Document** | Compare the storage architecture in ente... | 1836 (483) | 572 | **3463.7 ms** | **1928.3 ms** | 2140.3 ms | **1535.4 ms (1.8x faster)** |
| **Unsupported** | What is the secret quantum core warp pro... | 5859 (1542) | 4616 | **8332.3 ms** | **2277.8 ms** | 2377.7 ms | **6054.5 ms (3.7x faster)** |

---

## 2. Detailed Per-Case Analysis

### Case: Simple Factual (`1_simple_factual`)
- **Question**: *"What is the heliosphere?"*
- **Documents**: `['ss-high (1).pdf']`
- **Prompt Breakdown**:
  - System Instruction: `112` chars (~`29` tokens)
  - Context Size: `3428` chars (~`902` tokens)
  - Total Prompt: `4611` chars (~`1213` tokens)
- **Non-Streaming Timings (ms)**:
  - Total: Min `1401.69`, Max `14289.7`, Avg `5998.15`, Median `2303.07`
  - API Generation: Avg `1584.96` ms
  - Output Tokens: ~`113.33` tokens
  - Generation Rate: `76.29` tokens/sec
- **Streaming Timings (ms)**:
  - TTFT (Perceived): Min `1471.75`, Max `2932.95`, Avg `2136.23`, Median `2003.98`
  - API TTFT: Avg `1756.29` ms
  - Stream Generation Duration: Avg `580.09` ms
  - Total Request: Avg `2722.93` ms
  - Chunks Received: Avg `3.67` chunks
- **Sample Output**: *"The heliosphere is an enormous bubble created by the solar wind, which is a stream of charged gas blowing outward from t..."*

### Case: Conceptual (`2_conceptual`)
- **Question**: *"Explain the zero-trust security architecture and pre-retrieval tenant isolation in NexusAI."*
- **Documents**: `['architecture_spec.txt']`
- **Prompt Breakdown**:
  - System Instruction: `112` chars (~`29` tokens)
  - Context Size: `269` chars (~`71` tokens)
  - Total Prompt: `1519` chars (~`400` tokens)
- **Non-Streaming Timings (ms)**:
  - Total: Min `828.65`, Max `947.41`, Avg `902.55`, Median `931.58`
  - API Generation: Avg `848.29` ms
  - Output Tokens: ~`15` tokens
  - Generation Rate: `17.75` tokens/sec
- **Streaming Timings (ms)**:
  - TTFT (Perceived): Min `957.93`, Max `1305.27`, Avg `1163.08`, Median `1226.04`
  - API TTFT: Avg `1118.32` ms
  - Stream Generation Duration: Avg `14.47` ms
  - Total Request: Avg `1178.54` ms
  - Chunks Received: Avg `1.33` chunks
- **Sample Output**: *"I couldn't find that information in the uploaded document."*

### Case: Comparison (`3_comparison`)
- **Question**: *"What is the difference between gas giants and ice giants?"*
- **Documents**: `['ss-high (1).pdf']`
- **Prompt Breakdown**:
  - System Instruction: `112` chars (~`29` tokens)
  - Context Size: `5164` chars (~`1359` tokens)
  - Total Prompt: `6380` chars (~`1679` tokens)
- **Non-Streaming Timings (ms)**:
  - Total: Min `2346.5`, Max `2815.67`, Avg `2643.56`, Median `2768.52`
  - API Generation: Avg `1709.59` ms
  - Output Tokens: ~`132.33` tokens
  - Generation Rate: `78.58` tokens/sec
- **Streaming Timings (ms)**:
  - TTFT (Perceived): Min `1906.54`, Max `26571.33`, Avg `13157.02`, Median `10993.19`
  - API TTFT: Avg `12279.45` ms
  - Stream Generation Duration: Avg `391.1` ms
  - Total Request: Avg `13594.61` ms
  - Chunks Received: Avg `5.67` chunks
- **Sample Output**: *"Based on the provided document, the differences between gas giants and ice giants include:

* **Planets included:** Jupi..."*

### Case: Multi-Document (`4_multi_document`)
- **Question**: *"Compare the storage architecture in enterprise_storage.txt with the compute spec in benchmark_report.txt."*
- **Documents**: `['enterprise_storage.txt', 'benchmark_report.txt']`
- **Prompt Breakdown**:
  - System Instruction: `112` chars (~`29` tokens)
  - Context Size: `572` chars (~`151` tokens)
  - Total Prompt: `1836` chars (~`483` tokens)
- **Non-Streaming Timings (ms)**:
  - Total: Min `1399.16`, Max `6291.89`, Avg `3463.74`, Median `2700.17`
  - API Generation: Avg `3284.82` ms
  - Output Tokens: ~`139.33` tokens
  - Generation Rate: `63.5` tokens/sec
- **Streaming Timings (ms)**:
  - TTFT (Perceived): Min `1164.68`, Max `2509.75`, Avg `1928.34`, Median `2110.58`
  - API TTFT: Avg `1792.33` ms
  - Stream Generation Duration: Avg `205.35` ms
  - Total Request: Avg `2140.27` ms
  - Chunks Received: Avg `5.67` chunks
- **Sample Output**: *"Based on the provided documents, the storage architecture and compute performance specifications are as follows:

* **St..."*

### Case: Unsupported (`5_unsupported`)
- **Question**: *"What is the secret quantum core warp propulsion frequency of the Voyager spacecraft?"*
- **Documents**: `['ss-high (1).pdf']`
- **Prompt Breakdown**:
  - System Instruction: `112` chars (~`29` tokens)
  - Context Size: `4616` chars (~`1215` tokens)
  - Total Prompt: `5859` chars (~`1542` tokens)
- **Non-Streaming Timings (ms)**:
  - Total: Min `2071.99`, Max `18519.03`, Avg `8332.3`, Median `4405.88`
  - API Generation: Avg `7958.91` ms
  - Output Tokens: ~`15` tokens
  - Generation Rate: `4.46` tokens/sec
- **Streaming Timings (ms)**:
  - TTFT (Perceived): Min `1919.28`, Max `2977.54`, Avg `2277.82`, Median `1936.65`
  - API TTFT: Avg `1917.11` ms
  - Stream Generation Duration: Avg `79.61` ms
  - Total Request: Avg `2377.71` ms
  - Chunks Received: Avg `2` chunks
- **Sample Output**: *"I couldn't find that information in the uploaded document."*
