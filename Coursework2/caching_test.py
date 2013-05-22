"""Tests for the caching module."""

import unittest

from caching import Cache, SlotState


class FakeBus():
  """A fake implementation of the bus to be injected."""

  def add_cache(self, cache):
    pass

  def read_miss(self, cache_id, address):
    pass

  def write_miss(self, cache_id, address):
    pass


class FakeTracker():
  """A fake implementation of the tracker to be injected."""

  def add_cache(self, cache):
    pass

  def read_miss(self, cache_id, address, tag, slot_id, coherence_miss):
    pass

  def read_hit(self, cache_id, address, tag, slot_id):
    pass

  def write_miss(self, cache_id, address, tag, slot_id, coherence_miss):
    pass

  def write_hit(self, cache_id, address, tag, slot_id):
    pass


class CachingTest(unittest.TestCase):
  """Tests for the caching module."""

  # Default configuration. Individual tests may override.
  _NUMBER_OF_CACHE_LINES = 128
  _SIZE_OF_CACHE_LINE = 4

  def setUp(self):
    self.fake_bus = FakeBus()
    self.fake_tracker = FakeTracker()

    self.default_cache = Cache(
        0, # Cache id.
        CachingTest._NUMBER_OF_CACHE_LINES,
        CachingTest._SIZE_OF_CACHE_LINE,
        self.fake_bus,
        self.fake_tracker,
        debug_mode=False)

  def test_initialization(self):
    """Tests that a Cache is initialized properly."""

    # First, the default cache. 128 lines maps to 7 slot bits, 4 words per line
    # maps to 2 offset bits.
    self.assertEqual(self.default_cache.cache_id, 0)
    self.assertEqual(self.default_cache.slot_bits, 7)
    self.assertEqual(self.default_cache.offset_bits, 2)
    self.assertEqual(self.default_cache.bus, self.fake_bus)
    self.assertEqual(self.default_cache.tracker, self.fake_tracker)

    # A different sized cache. 512 lines ==> 9 slot bits, 1 word per line ==> 0
    # offset bits.
    cache = Cache(1, 512, 1, self.fake_bus, self.fake_tracker, debug_mode=False)
    self.assertEqual(cache.cache_id, 1)
    self.assertEqual(cache.slot_bits, 9)
    self.assertEqual(cache.offset_bits, 0)

    # One more. 32 lines ==> 5 slot bits, 32 word per line ==> 5 offset bits.
    cache = Cache(2, 32, 32, self.fake_bus, self.fake_tracker, debug_mode=False)
    self.assertEqual(cache.cache_id, 2)
    self.assertEqual(cache.slot_bits, 5)
    self.assertEqual(cache.offset_bits, 5)

    # Finally, test the error-throwing cases: non-powers of two.

    with self.assertRaises(ValueError):
        Cache(2, 15, 32, self.fake_bus, self.fake_tracker, debug_mode=False)

    with self.assertRaises(ValueError):
        Cache(2, 32, 15, self.fake_bus, self.fake_tracker, debug_mode=False)

    with self.assertRaises(ValueError):
        Cache(2, -2, 32, self.fake_bus, self.fake_tracker, debug_mode=False)

    with self.assertRaises(ValueError):
        Cache(2, 32, -2, self.fake_bus, self.fake_tracker, debug_mode=False)

  def test_address_placement(self):
    """Tests that addresses are mapped to the correct slot.

    Note that this overlaps with testing actual MSI protocol, but that
    is not the aim here: only the actual breakdown of the address is
    of interest. The check for SHARED is only to make sure that the line
    is actually in the cache."""

    # First test the default setup: 128 lines, 4 words per line.

    # Address 5: slot 1, tag 0.
    self.default_cache.read(5)
    line = self.default_cache.get_cache_line(1)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 0)

    # Address 522: slot 2, tag 1.
    self.default_cache.read(522)
    line = self.default_cache.get_cache_line(2)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 1)

    # Address 523: still slot 2, tag 1.
    self.default_cache.read(523)
    line = self.default_cache.get_cache_line(2)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 1)

    # Address 2571: also slot 2, but tag 5.
    self.default_cache.read(2571)
    line = self.default_cache.get_cache_line(2)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 5)

    # Now test another cache: 16 lines, 8 words per line.
    cache = Cache(1, 16, 8, self.fake_bus, self.fake_tracker, debug_mode=False)

    # Address 5: slot 0, tag 0.
    cache.read(5)
    line = cache.get_cache_line(0)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 0)

    # Address 522: slot 1, tag 4.
    cache.read(522)
    line = cache.get_cache_line(1)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 4)

    # Address 527: still slot 1, tag 4.
    cache.read(527)
    line = cache.get_cache_line(1)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 4)

    # Address 528: slot 2, still tag 4.
    cache.read(528)
    line = cache.get_cache_line(2)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 4)

    # Address 2571: also slot 1, but tag 20.
    cache.read(2571)
    line = cache.get_cache_line(1)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 20)

  def test_local_accesses(self):
    """Tests that local accesses adhere to the MSI protocol."""

    # State transitions should be:
    #   INVALID + read ==> read_miss + SHARED.
    #   INVALID + write ==> write_miss + MODIFIED.
    #   SHARED + read ==> read_hit + SHARED.
    #   SHARED + write ==> write_miss + MODIFIED.
    #   MODIFIED + read ==> read_hit + MODIFIED.
    #   MODIFIED + write ==> write_hit + MODIFIED.

    # INVALID + read.
    hit = self.default_cache.read(10)
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(2) # Address 10 ==> slot 2.
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertFalse(line.written_to)

    # INVALID + write.
    hit = self.default_cache.write(20)
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(5) # Address 20 ==> slot 5.
    self.assertEqual(line.state, SlotState.MODIFIED)
    self.assertTrue(line.written_to)

    # SHARED + read.
    self.default_cache.read(30) # Prime the cache.
    hit = self.default_cache.read(31)
    self.assertTrue(hit)
    line = self.default_cache.get_cache_line(7) # Address 31 ==> slot 7.
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertFalse(line.written_to)

    # SHARED + write.
    self.default_cache.read(40) # Prime the cache.
    hit = self.default_cache.write(41)
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(10) # Address 41 ==> slot 10.
    self.assertEqual(line.state, SlotState.MODIFIED)
    self.assertTrue(line.written_to)

    # MODIFIED + read
    self.default_cache.write(50) # Prime the cache.
    hit = self.default_cache.read(51)
    self.assertTrue(hit)
    line = self.default_cache.get_cache_line(12) # Address 51 ==> slot 12.
    self.assertEqual(line.state, SlotState.MODIFIED)
    self.assertTrue(line.written_to)

    # MODIFIED + write
    self.default_cache.write(60) # Prime the cache.
    hit = self.default_cache.write(61)
    self.assertTrue(hit)
    line = self.default_cache.get_cache_line(15) # Address 61 ==> slot 15.
    self.assertEqual(line.state, SlotState.MODIFIED)
    self.assertTrue(line.written_to)

    # Mismatching tags in any non-INVALID state should be equivalent to INVALID.

    # SHARED + read.
    self.default_cache.read(30) # Prime the cache.
    hit = self.default_cache.read(2590) # Access a different tag.
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(7) # Address 30|2590 ==> slot 7.
    self.assertFalse(line.written_to)

    # SHARED + write.
    self.default_cache.read(40) # Prime the cache.
    hit = self.default_cache.write(10280) # Access a different tag.
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(10) # Address 40|10280 ==> slot 10.
    self.assertTrue(line.written_to)

    # MODIFIED + read
    self.default_cache.write(50) # Prime the cache.
    hit = self.default_cache.read(5682) # Access a different tag.
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(12) # Address 50|5682 ==> slot 12.
    self.assertFalse(line.written_to) # 5682 has only been read.

    # MODIFIED + write
    self.default_cache.write(60) # Prime the cache.
    hit = self.default_cache.write(1596) # Access a different tag.
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(15) # Address 60|1596 ==> slot 12.
    self.assertTrue(line.written_to)

  def test_remote_accesses(self):
    """Tests that remote accesses adhere to the MSI protocol."""

    # State transitions should be:
    #   INVALID + remote read miss ==> INVALID.
    #   INVALID + remote write miss ==> INVALID.
    #   SHARED + remote read miss ==> SHARED.
    #   SHARED + remote write miss ==> INVALID.
    #   MODIFIED + remote read miss ==> SHARED.
    #   MODIFIED + remote write miss ==> INVALID.

    # INVALID + remote read miss.
    self.default_cache.notify_read_miss(10)
    line = self.default_cache.get_cache_line(2) # Address 10 ==> slot 2.
    self.assertEqual(line.state, SlotState.INVALID)
    self.assertEqual(line.previous_state, None)

    # INVALID + remote write miss.
    self.default_cache.notify_write_miss(20)
    line = self.default_cache.get_cache_line(5) # Address 20 ==> slot 5.
    self.assertEqual(line.state, SlotState.INVALID)
    self.assertEqual(line.previous_state, None)

    # SHARED + remote read miss.
    self.default_cache.read(30) # Prime the cache.
    self.default_cache.notify_read_miss(31)
    line = self.default_cache.get_cache_line(7) # Address 31 ==> slot 7.
    self.assertEqual(line.state, SlotState.SHARED)
    # The previous_state variable tracks the previous state for coherence-caused
    # changes, so won't have changed here.
    self.assertEqual(line.previous_state, SlotState.INVALID)

    # SHARED + remote write miss.
    self.default_cache.read(40) # Prime the cache.
    self.default_cache.notify_write_miss(41)
    line = self.default_cache.get_cache_line(10) # Address 41 ==> slot 10.
    self.assertEqual(line.state, SlotState.INVALID)
    self.assertEqual(line.previous_state, SlotState.SHARED)

    # MODIFIED + remote read miss.
    self.default_cache.write(50) # Prime the cache.
    self.default_cache.notify_read_miss(51)
    line = self.default_cache.get_cache_line(12) # Address 51 ==> slot 12.
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.previous_state, SlotState.MODIFIED)

    # MODIFIED + remote write miss.
    self.default_cache.write(60) # Prime the cache.
    self.default_cache.notify_write_miss(61)
    line = self.default_cache.get_cache_line(15) # Address 61 ==> slot 15.
    self.assertEqual(line.state, SlotState.INVALID)
    self.assertEqual(line.previous_state, SlotState.MODIFIED)

    # Mismatching tags should not cause a change.

    # SHARED + write: shouldn't go to INVALID.
    self.default_cache.read(30) # Prime the cache.
    self.default_cache.notify_write_miss(2590) # Write miss for different tag.
    line = self.default_cache.get_cache_line(7) # Address 30|2590 ==> slot 7.
    self.assertEqual(line.state, SlotState.SHARED)

    # MODIFIED + read: shouldn't go to SHARED.
    self.default_cache.write(40) # Prime the cache.
    self.default_cache.notify_read_miss(10280) # Read miss for different tag.
    line = self.default_cache.get_cache_line(10) # Address 40|10280 ==> slot 10.
    self.assertEqual(line.state, SlotState.MODIFIED)

  def test_write_tracking(self):
    """Tests that writes to a cache line are correctly tracked."""

    # Basic case: line not written to.
    self.default_cache.read(10)
    self.default_cache.read(11)
    line = self.default_cache.get_cache_line(2) # Address 10 ==> slot 2.
    self.assertFalse(line.written_to)

    # Basic case: line written to.
    self.default_cache.read(20)
    self.default_cache.write(21)
    self.default_cache.read(21)
    line = self.default_cache.get_cache_line(5) # Address 20 ==> slot 5.
    self.assertTrue(line.written_to)

    # Basic case: line written to, then flushed.
    self.default_cache.read(30)
    self.default_cache.write(31)
    self.default_cache.read(543) # Cache slot flushed.
    line = self.default_cache.get_cache_line(7) # Address 30|543 ==> slot 7.
    self.assertFalse(line.written_to)

    # Basic case: line written to, then flushed, then re-filled.
    self.default_cache.read(40)
    self.default_cache.write(41)
    self.default_cache.read(553) # Cache slot flushed.
    self.default_cache.read(40) # Re-filled.
    line = self.default_cache.get_cache_line(10) # Address 50|553 ==> slot 10.
    self.assertFalse(line.written_to)

    # More complex case. Line written to, then flushed by external processor.
    self.default_cache.write(50)
    self.default_cache.notify_write_miss(51) # Flush.
    line = self.default_cache.get_cache_line(12) # Address 50 ==> slot 12
    self.assertTrue(line.written_to)

    # More complex case. Line written to, then set to SHARED by external processor.
    self.default_cache.write(60)
    self.default_cache.notify_read_miss(61) # Set to SHARED.
    line = self.default_cache.get_cache_line(15) # Address 60 ==> slot 15
    self.assertTrue(line.written_to)


if __name__ == "__main__":
  unittest.main()