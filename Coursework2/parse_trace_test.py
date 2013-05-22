"""Tests for the coursework."""

import contextlib
from cStringIO import StringIO
import sys
import unittest

from caching import SlotState
from parse_trace import SimulationEnvironment


"""A context manager that allows us to capture print statements, i.e.

>> with capture_output() as out:
>>   print "Hello, World!"
>> out
['Hello, World!\n', '']
"""
@contextlib.contextmanager
def capture_output():
  old_out, old_err = sys.stdout, sys.stderr
  try:
    out = [StringIO(), StringIO()]
    sys.stdout, sys.stderr = out
    yield out
  finally:
    sys.stdout, sys.stdout = old_out, old_err
    out[0] = out[0].getvalue()
    out[1] = out[1].getvalue()


class SimulationTest(unittest.TestCase):
  """Validation tests for the simulator, based on trace files.

  Tests are generally defined in the trace files themselves; if you do not
  understand the purpose of a test it is best to refer to the trace file it
  simulates."""

  # All tests use the same simulation configuration.
  _NUMBER_OF_PROCESSORS = 4
  _NUMBER_OF_CACHE_LINES = 128
  _SIZE_OF_CACHE_LINE = 4

  def setUp(self):
    self.simulation = SimulationEnvironment(
        SimulationTest._NUMBER_OF_PROCESSORS,
        SimulationTest._NUMBER_OF_CACHE_LINES,
        SimulationTest._SIZE_OF_CACHE_LINE,
        # Always turn on debug mode, so that the sanity check in
        # SimulationEnvironment.simulate() execute.
        debug_mode=True)

  def test_local_behaviour(self):
    with capture_output():
      self.simulation.simulate("test_traces/local_trace.out")

    # Grab the cache for processor 0.
    cache = self.simulation.caches[0]
    cache_lines = cache.cache_lines

    # Slot 0 should be SHARED, tag == 0
    slot = cache_lines[0]
    self.assertEqual(slot.state, SlotState.SHARED)
    self.assertEqual(slot.tag, 0)

    # Slot 1 should be SHARED, tag == 1
    slot = cache_lines[1]
    self.assertEqual(slot.state, SlotState.SHARED)
    self.assertEqual(slot.tag, 1)

    # Slot 2 should be MODIFIED, tag == 2
    slot = cache_lines[2]
    self.assertEqual(slot.state, SlotState.MODIFIED)
    self.assertEqual(slot.tag, 2)

    # Slot 3 should be MODIFIED, tag == 3
    slot = cache_lines[3]
    self.assertEqual(slot.state, SlotState.MODIFIED)
    self.assertEqual(slot.tag, 3)

    # Slot 4 should be MODIFIED, tag == 4
    slot = cache_lines[4]
    self.assertEqual(slot.state, SlotState.MODIFIED)
    self.assertEqual(slot.tag, 4)

    # Slot 5 should be MODIFIED, tag == 5
    slot = cache_lines[5]
    self.assertEqual(slot.state, SlotState.MODIFIED)
    self.assertEqual(slot.tag, 5)

    # Slot 6 should be MODIFIED, tag == 6
    slot = cache_lines[6]
    self.assertEqual(slot.state, SlotState.MODIFIED)
    self.assertEqual(slot.tag, 6)

    # Slot 7 should INVALID (not accessed), tag == None
    slot = cache_lines[7]
    self.assertEqual(slot.state, SlotState.INVALID)
    self.assertEqual(slot.tag, None)

  def test_remote_behaviour(self):
    with capture_output():
      self.simulation.simulate("test_traces/remote_trace.out")

    # Grab the cache for processor 0.
    cache = self.simulation.caches[0]
    cache_lines = cache.cache_lines

    # Slot 0 should be INVALID, tag == 0
    slot = cache_lines[0]
    self.assertEqual(slot.state, SlotState.INVALID)
    self.assertEqual(slot.tag, 0)

    # Slot 1 should be SHARED, tag == 1
    slot = cache_lines[1]
    self.assertEqual(slot.state, SlotState.SHARED)
    self.assertEqual(slot.tag, 1)

    # Slot 2 should be SHARED, tag == 2
    slot = cache_lines[2]
    self.assertEqual(slot.state, SlotState.SHARED)
    self.assertEqual(slot.tag, 2)

    # Slot 3 should be INVALID, tag == 3
    slot = cache_lines[3]
    self.assertEqual(slot.state, SlotState.INVALID)
    self.assertEqual(slot.tag, 3)

    # Slot 4 should be INVALID, tag == None (not accessed)
    slot = cache_lines[4]
    self.assertEqual(slot.state, SlotState.INVALID)
    self.assertEqual(slot.tag, None)

    # Slot 5 should be INVALID, tag == None (not accessed)
    slot = cache_lines[5]
    self.assertEqual(slot.state, SlotState.INVALID)
    self.assertEqual(slot.tag, None)

  def test_miss_tracking(self):
    with capture_output():
      self.simulation.simulate("test_traces/miss_rate_trace.out")

    # Check processor 0.
    stats = self.simulation.tracker.get_cache_stats(0)
    self.assertEqual(stats["accesses"], 20)
    self.assertEqual(stats["misses"], 8)
    self.assertEqual(stats["read_misses"], 3)
    self.assertEqual(stats["write_misses"], 5)

    # Check processor 1.
    stats = self.simulation.tracker.get_cache_stats(1)
    self.assertEqual(stats["accesses"], 1)
    self.assertEqual(stats["misses"], 1)
    self.assertEqual(stats["read_misses"], 1)

  def test_coherence_miss_tracking(self):
    with capture_output():
      self.simulation.simulate("test_traces/coherence_miss_rate_trace.out")

    # Check processor 0.
    stats = self.simulation.tracker.get_cache_stats(0)
    self.assertEqual(stats["misses"], 2)
    self.assertEqual(stats["coherence_misses"], 0)

    # Check processor 1.
    stats = self.simulation.tracker.get_cache_stats(1)
    self.assertEqual(stats["misses"], 4)
    self.assertEqual(stats["coherence_misses"], 1)

    # Check processor 2.
    stats = self.simulation.tracker.get_cache_stats(2)
    self.assertEqual(stats["misses"], 5)
    self.assertEqual(stats["coherence_misses"], 4)

  def test_address_tracking(self):
    with capture_output():
      self.simulation.simulate("test_traces/address_trace.out")

    # Get the statistics.
    stats = self.simulation.tracker.get_general_stats()

    # Check that the addresses are being tracked correctly.
    self.assertAlmostEqual(stats["addresses"], 8)
    self.assertAlmostEqual(stats["addressed_by_one_processor"], 2)
    self.assertAlmostEqual(stats["addressed_by_two_processors"], 2)
    self.assertAlmostEqual(stats["addressed_by_more_than_two_processors"], 4)


if __name__ == "__main__":
  unittest.main()