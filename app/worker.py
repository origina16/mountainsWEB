import threading
import time
import queue
import logging

from app.distance import calculate_route_distance, get_route_stats

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Background worker for async task processing."""

    def __init__(self):
        self._task_queue = queue.Queue()
        self._running = False
        self._thread = None
        self._results = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Background worker started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Background worker stopped")

    def _run(self):
        while self._running:
            try:
                task_id, func, args, kwargs = self._task_queue.get(timeout=1)
                try:
                    result = func(*args, **kwargs)
                    self._results[task_id] = {"status": "done", "result": result}
                except Exception as e:
                    self._results[task_id] = {"status": "error", "error": str(e)}
                finally:
                    self._task_queue.task_done()
            except queue.Empty:
                continue

    def submit(self, task_id, func, *args, **kwargs):
        self._task_queue.put((task_id, func, args, kwargs))
        self._results[task_id] = {"status": "pending"}
        return task_id

    def get_result(self, task_id):
        return self._results.get(task_id, {"status": "unknown"})


worker = BackgroundWorker()


def async_calculate_distance(points):
    """Calculate distance in background thread."""
    time.sleep(0.1)
    return calculate_route_distance(points)


def async_get_stats(points):
    """Get route stats in background thread."""
    time.sleep(0.1)
    return get_route_stats(points)


def async_batch_process(routes_data):
    """Process multiple routes in parallel."""
    results = []
    lock = threading.Lock()

    def process_one(item):
        route_id = item["id"]
        points = item["points"]
        dist = calculate_route_distance(points)
        stats = get_route_stats(points)
        with lock:
            results.append({"id": route_id, "distance": dist, "stats": stats})

    threads = []
    for item in routes_data:
        t = threading.Thread(target=process_one, args=(item,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return sorted(results, key=lambda x: x["id"])
