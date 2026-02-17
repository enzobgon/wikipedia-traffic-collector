#!/usr/bin/env python3
# Wikipedia VPN Traffic Collector (OpenVPN by default)

# Capture encrypted VPN traffic while generating reproducible, configurable browsing behavior.
# This script starts a packet-sniffing thread (Scapy) and, in parallel, automates random Wikipedia navigation (Selenium), producing PCAP files.

# Key improvements over a naive sniff():
# - Reliable stop behavior: sniff() stop_filter is only evaluated when packets arrive.
# - Configurable behavior via CLI flags (scroll/read/click probability).

from __future__ import annotations

from dataclasses import dataclass # Used to group "Behavior" classes.
from datetime import datetime
import argparse  # Bash paramns.
import logging 
import os # For mkdir/root user.
import random 
import threading
import time
from typing import Tuple, Optional, List

from scapy.all import sniff, wrpcap  # sniff() for traffic capture / wrpcap() for create .pcap files.

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("wikipedia_traffic_collector")

# Global flag used to stop capture thread.
stop_capture_flag = threading.Event()

# Aux
# Random number between min/max interval setted.
def rand_range(r: Tuple[float, float]) -> float:
    a, b = r
    return random.uniform(a, b)

def randint_range(r: Tuple[int, int]) -> int:
    a, b = r
    return random.randint(a, b)

# Default human-like navigation behavior (be free to change any configuration).
@dataclass(frozen=True)
class Behavior:
  
    # Page load / reading.
    page_load_wait_s: Tuple[float, float] = (2.5, 5.5)
    read_time_s: Tuple[float, float] = (2.0, 6.0)

    # Scrolling.
    scrolls_per_page: Tuple[int, int] = (2, 4)
    scroll_px: Tuple[int, int] = (400, 900)
    scroll_pause_s: Tuple[float, float] = (1.5, 3.0)

    # Clicking internal links.
    click_probability: float = 0.25     # Probability to click an internal link on a page.
    max_clicks_per_page: int = 1        # Hard cap per page.

    # Small idle moments.
    idle_probability: float = 0.15
    idle_time_s: Tuple[float, float] = (2.0, 6.0)

# Create the default config web.driver.
def build_driver(headless: bool, chromedriver_path: Optional[str]) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")  # Modern headless mode.
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(chromedriver_path) if chromedriver_path else Service()
    return webdriver.Chrome(service=service, options=options)

# Packet capture
def capture_packets(interface: str, filename: str, bpf_filter: str, poll_timeout_s: float = 1.0) -> None:

    # Capture packets on the given interface using a BPF filter (only OpenVPN "udp port 1194") until stop_capture_flag is set.

    # NOTE:
    # scapy sniff(stop_filter=...) only checks stop_filter when packets arrive.
    # If traffic becomes silent, the thread may hang waiting for packets.
    # Looping with a short timeout makes stopping reliable.

    logger.info("Starting capture on interface=%s | filter='%s'", interface, bpf_filter)
    captured: List = []

    try:
        while not stop_capture_flag.is_set():
            pkts = sniff(iface=interface, filter=bpf_filter, timeout=poll_timeout_s)
            if pkts:
                captured.extend(pkts)

        wrpcap(filename, captured)
        logger.info("Capture finished. Saved %d packets to %s", len(captured), filename)

    except Exception as e:
        logger.exception("Capture error: %s", e)

# Wikipedia simulation
def maybe_idle(behavior: Behavior) -> None:
    # Occasionally pause to simulate human idle time.
    if random.random() < behavior.idle_probability:
        t = rand_range(behavior.idle_time_s)
        logger.info("  Idle for %.2fs (human pause)", t)
        time.sleep(t)

# Attempt to click a random internal Wikipedia link (like an image or other page).
def click_random_internal_link(driver: webdriver.Chrome, max_tries: int = 2) -> bool:
  
    for _ in range(max_tries):
        try:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href^='/wiki/']")
            links = [a for a in links if a.is_displayed()]
            if not links:
                return False

            random.choice(links).click()
            return True
        except WebDriverException:
            continue
    return False


def simulate_wikipedia(pages: int, behavior: Behavior, headless: bool, chromedriver_path: Optional[str]) -> None:

    # I'm using the official random generation page from Wikipedia web site (in portuguese-br).
    random_url = "https://pt.wikipedia.org/wiki/Especial:Aleatória"
    driver = build_driver(headless=headless, chromedriver_path=chromedriver_path)

    try:
        for i in range(pages):
            logger.info("Page %d/%d: open random article", i + 1, pages)
            driver.get(random_url)

            time.sleep(rand_range(behavior.page_load_wait_s))
            maybe_idle(behavior)

            clicks_done = 0
            if behavior.click_probability > 0:
                if random.random() < behavior.click_probability and clicks_done < behavior.max_clicks_per_page:
                    ok = click_random_internal_link(driver)
                    if ok:
                        clicks_done += 1
                        logger.info("  Clicked an internal link (%d/%d)", clicks_done, behavior.max_clicks_per_page)
                        time.sleep(rand_range(behavior.page_load_wait_s))
                        maybe_idle(behavior)

            read_t = rand_range(behavior.read_time_s)
            logger.info("  Reading for %.2fs", read_t)
            time.sleep(read_t)

            num_scrolls = randint_range(behavior.scrolls_per_page)
            for s in range(num_scrolls):
                px = randint_range(behavior.scroll_px)
                logger.info("  Scroll %d/%d: down %d px", s + 1, num_scrolls, px)
                driver.execute_script("window.scrollBy(0, arguments[0]);", px)
                time.sleep(rand_range(behavior.scroll_pause_s))
                maybe_idle(behavior)

        logger.info("Wikipedia browsing finished.")

    finally:
        driver.quit()
      
# CLI.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture VPN traffic (OpenVPN by default) while browsing random Wikipedia pages."
    )

    # Core capture options.
    parser.add_argument("-i", "--interface", default="enp0s8", help="Network interface to sniff (e.g., enp0s8)")
    parser.add_argument("--filter", default="udp port 1194", help="BPF filter (default: 'udp port 1194')")
    parser.add_argument("-c", "--cycles", type=int, default=1, help="Number of capture/browse cycles (default: 1)")
    parser.add_argument("-p", "--pages", type=int, default=10, help="Random Wikipedia pages per cycle (default: 10)")


    # Output naming.
    parser.add_argument("--outdir", default="capturas", help="Output directory for PCAP files")
    parser.add_argument("--prefix", default="wiki_traffic", help="PCAP filename prefix (default: wiki_traffic)")

    # Selenium options.
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    parser.add_argument("--chromedriver-path", default=None, help="Custom chromedriver path (optional)")

    # Behavior knobs.
    parser.add_argument("--read-min", type=float, default=2.0, help="Min reading time in seconds (default: 2.0)")
    parser.add_argument("--read-max", type=float, default=6.0, help="Max reading time in seconds (default: 6.0)")

    parser.add_argument("--scrolls-min", type=int, default=2, help="Min scrolls per page (default: 2)")
    parser.add_argument("--scrolls-max", type=int, default=4, help="Max scrolls per page (default: 4)")

    parser.add_argument("--scroll-px-min", type=int, default=400, help="Min scroll pixels (default: 400)")
    parser.add_argument("--scroll-px-max", type=int, default=900, help="Max scroll pixels (default: 900)")

    parser.add_argument("--click-prob", type=float, default=0.25, help="Probability to click an internal link (0..1)")
    parser.add_argument("--max-clicks", type=int, default=1, help="Max internal link clicks per page (default: 1)")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if os.geteuid() != 0:
        logger.error("Run with sudo: sudo python3 wikipedia_traffic_collector.py ...")
        raise SystemExit(1)

    os.makedirs(args.outdir, exist_ok=True)

    behavior = Behavior(
        read_time_s=(args.read_min, args.read_max),
        scrolls_per_page=(args.scrolls_min, args.scrolls_max),
        scroll_px=(args.scroll_px_min, args.scroll_px_max),
        click_probability=max(0.0, min(1.0, args.click_prob)),
        max_clicks_per_page=max(0, args.max_clicks),
    )

    try:
        for c in range(args.cycles):
            logger.info("=" * 60)
            logger.info("Cycle %d/%d", c + 1, args.cycles)
            logger.info("=" * 60)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pcap_path = os.path.join(args.outdir, f"{args.prefix}_{timestamp}.pcap")

            stop_capture_flag.clear()

            capture_thread = threading.Thread(
                target=capture_packets,
                args=(args.interface, pcap_path, args.filter),
                daemon=True,
            )
            capture_thread.start()

            time.sleep(2)

            simulate_wikipedia(
                pages=args.pages,
                behavior=behavior,
                headless=args.headless,
                chromedriver_path=args.chromedriver_path,
            )

            stop_capture_flag.set()
            logger.info("Waiting capture thread to finish...")
            capture_thread.join()

            logger.info("✓ Cycle %d completed successfully!", c + 1)

            if c < args.cycles - 1:
                time.sleep(3)

    except KeyboardInterrupt:
        logger.warning("Interrupted by user (Ctrl+C).")
        stop_capture_flag.set()

    except Exception as e:
        logger.exception("Runtime error: %s", e)
        stop_capture_flag.set()

    finally:
        logger.info("Done.")


if __name__ == "__main__":
    main()
