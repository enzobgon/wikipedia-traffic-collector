# Wikipedia VPN Traffic Capture

This project is part of a research workflow focused on **encrypted traffic classification using Machine Learning**.

The objective is to capture VPN-encrypted traffic (OpenVPN by default) while generating reproducible and configurable browsing behavior on Wikipedia.  

---

## Overview

This script:

- Starts a packet capture thread using Scapy.
- Applies a BPF filter (default: `udp port 1194`).
- Automates Wikipedia browsing using Selenium.
- Generates timestamped PCAP files.
- Allows configurable "human-like" navigation patterns.

The design ensures reproducibility and structured dataset generation for ML experiments.


## Features

- Reliable capture stop mechanism (works even during traffic silence).
- Configurable browsing behavior:
  - Reading time
  - Scroll intensity
  - Scroll distance
  - Internal link click probability
- Multi-cycle execution with automatic PCAP separation.
- Clean, organized logging output.



## Requirements

### System

- Linux (recommended)
- Root privileges to capture packets

### Python Packages

Install dependencies:

```bash
pip install scapy selenium
```

### Chrome + ChromeDriver

You must have:

- Google Chrome (or Chromium)
- ChromeDriver available in PATH

Verify:

```bash
chromedriver --version
google-chrome --version
```

---

## How to Run

The script is executed via CLI (Command Line Interface).

General syntax:

```bash
sudo python3 wikipedia_traffic_collector.py [OPTIONS]
```

### Core Parameters

| Flag | Description |
|------|------------|
| `-i`, `--interface` | Network interface to sniff (e.g., enp0s8) |
| `-c`, `--cycles` | Number of capture cycles |
| `-p`, `--pages` | Number of random Wikipedia pages per cycle |
| `--filter` | BPF filter (default: `udp port 1194`) |
| `--headless` | Run browser without GUI |
| `--outdir` | Output directory for PCAP files |
| `--prefix` | Prefix for generated PCAP filenames |


### Behavior Parameters (Human-like Control)

| Flag | Description |
|------|------------|
| `--read-min` | Minimum reading time per page (seconds) |
| `--read-max` | Maximum reading time per page (seconds) |
| `--scrolls-min` | Minimum number of scrolls per page |
| `--scrolls-max` | Maximum number of scrolls per page |
| `--scroll-px-min` | Minimum scroll distance in pixels |
| `--scroll-px-max` | Maximum scroll distance in pixels |
| `--click-prob` | Probability (0.0–1.0) of clicking an internal Wikipedia link |
| `--max-clicks` | Maximum number of internal link clicks per page |

## Example

Run a single cycle with 10 pages:

```bash
sudo python3 wikipedia_traffic_collector.py -i enp0s8 -c 1 -p 10
```

This configuration:

- Capture traffic on interface `enp0s8`
- Execute 1 cycle
- Open 10 random Wikipedia pages
- Save one PCAP file


---

### Complete Example

```bash
sudo python3 wikipedia_traffic_collector.py \
    -i enp0s8 \
    -c 3 \
    -p 15 \
    --read-min 5 --read-max 12 \
    --scrolls-min 2 --scrolls-max 5 \
    --scroll-px-min 400 --scroll-px-max 1000 \
    --click-prob 0.3 \
    --max-clicks 1 \
    --headless
```

This configuration:

- Runs 3 capture cycles
- Opens 15 pages per cycle
- Simulates reading between 5 and 12 seconds
- Performs 2–5 scrolls per page
- Scroll distance varies between 400–1000 pixels
- Has a 30% chance of clicking one internal link
- Runs without opening a visible browser window

This produces a more realistic browsing pattern and increases traffic variability.

---

## Experimental Recommendation

For reproducible datasets:

- Keep behavior parameters constant across runs.
- Vary only one parameter at a time when conducting controlled experiments.
- Document CLI parameters used for each dataset.

---

## Disclaimer

This tool is intended for academic and authorized research purposes only.  
Only capture traffic on networks and systems where you have explicit permission.
