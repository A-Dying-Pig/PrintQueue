# PrintQueue's Analysis Program
The analysis program consists of three parts:
* `TimeWindows.py`: read raw register values and execute queries.
* `GroundTruth.py`: read INT data and return ground truth.
* `QueueMonitor.py`: read raw register values and construct the queue stack.

Folder `TW_RAW` stores the raw register values of time windows and corresponding INT data.
Folder `QM_RAW` stores the raw register values of queue monitor.
The register values and INT data are stored in the `binary` form.


The code is tested under `Python3.8` and `Python 3.9`. Run `pip3 -m install -r requirements.txt` to install dependencies.
To compare time windows with the related works, run the main program in the `GroundTruth.py`