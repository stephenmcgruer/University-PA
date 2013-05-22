"""The bus module."""


import random


class Bus:
  """Represents the system bus, attached to the caches."""

  def __init__(self):
    self.caches = []

  def add_cache(self, cache):
    """Add a cache to the bus."""

    self.caches.append(cache)

  def add_caches(self, new_caches):
    """Add a list of caches to the bus."""

    for cache in new_caches:
      self.caches.append(cache)

  def read_miss(self, cache_id, address):
    """Instruct the bus to notify the caches of a read miss to an address.

    The cache_id argument identifies the cache which issued the read miss;
    all caches which do not have that id are informed of the miss.

    Caches are notified in a random order.

    Returns true if the cache line would have to be fetched from main memory."""

    read_from_main_memory = True

    for cache in self.caches:
      if cache.cache_id != cache_id:
        has_address = cache.notify_read_miss(address)
        if has_address:
          read_from_main_memory = False

    return read_from_main_memory

  def write_miss(self, cache_id, address):
    """Instruct the bus to notify the caches of a write miss to an address.

    The cache_id argument identifies the cache which issued the write miss;
    all caches which do not have that id are informed of the miss.

    Caches are notified in a random order."""

    for cache in self.caches:
      if cache.cache_id != cache_id:
        cache.notify_write_miss(address)