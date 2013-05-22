import math
import matplotlib.pyplot as plt
import numpy as np
import sys

def main():
  if len(sys.argv) != 2:
    print "Usage: %s data_file" % sys.argv[0]
    return

  # 3 stats in the line info graph. 
  N = 3

  data = []
  with open(sys.argv[1], "r") as f:
    for line in f:
      stripped_line = line.strip()
      parts = stripped_line.split()
      if len(parts) != N:
        raise ValueError(
            "Unexpected number of parts in line '%s'" % stripped_line)
      data.append(map(float, parts))

  if len(data) != 4:
    raise ValueError("Expected 4 lines, found %s." % len(data))

  indices = np.arange(N)
  width = 0.2

  fig = plt.figure()
  ax = fig.add_subplot(111)

  colors = ['#EF2929', '#729FCF', '#F57900', '#73D216']

  names = []
  rects = []
  max_y = 0.0
  for (i, values) in enumerate(data):
    left = indices + (i * width)
    color = colors[i % len(colors)]
    rects.append(ax.bar(left, values, width, color=color))

    names.append("Cache %s" % i)

    max_y = max(max_y, max(values))

  ax.set_title("Per-Cache Line Statistics")
  ax.set_ylabel('Percentage')
  ax.set_xticks(indices + (2 * width))
  ax.set_xticklabels(('Private Line\nAccess Rate',
      'Shared Read-only\nAccess Rate',
      'Shared Read-Write\nAccess Rate'))

  # Round up the Y value to next 10.
  y_limit = int(math.ceil(max_y / 10)) * 10

  ax.axis([-0.1, N, 0, 100])

  ax.legend((rects[0][0], rects[1][0], rects[2][0], rects[3][0]), names,
      loc='best')

  plt.show()

if __name__ == "__main__":
  main()