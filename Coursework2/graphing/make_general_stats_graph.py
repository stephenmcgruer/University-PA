import math
import matplotlib.pyplot as plt
import numpy as np
import sys

def main():
  if len(sys.argv) != 2:
    print "Usage: %s data_file" % sys.argv[0]
    return

  # 6 stats in the line info graph. 
  N = 6

  with open(sys.argv[1], "r") as f:
    lines = [line.strip() for line in f]
    if len(lines) != 1:
      raise ValueError("Expected 1 line, found %s." % len(data))
    values = map(float, lines[0].split())
    if len(values) != N:
      raise ValueError("Unexpected number of parts in line '%s'" % lines[0])

  indices = np.arange(N)
  width = 1

  fig = plt.figure()
  ax = fig.add_subplot(111)
  ax.bar(indices, values, width, color='#729FCF')

  ax.set_title("General Statistics")
  ax.set_ylabel('Percentage')
  ax.set_yticks(range(0, 101, 10))
  ax.set_xticks(indices + 0.5)
  ax.set_xticklabels(('Private Line\nAccess Rate',
      'Shared\nRead-only\nAccess Rate',
      'Shared\nRead-Write\nAccess Rate',
      'Addresses\naccessed by\n1 processor',
      'Addresses\naccessed by\n2 processors',
      'Addresses\naccessed by\n>2 processors'))

  # Round up the Y value to next 10.
  max_y = max(values)
  y_limit = int(math.ceil(max_y / 10)) * 10

  ax.axis([-0.1, N, 0, 100])

  plt.show()

if __name__ == "__main__":
  main()