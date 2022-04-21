# PrintQueue's Analysis Program
The analysis program consists of three parts:
* `TimeWindows.py`: read binary files of register values and execute queries.
* `GroundTruth.py`: read binary files of INT data and return ground truth.
* `QueueMonitor.py`: read binary files of register values and construct the queue stack.

The layout of binary files can be found in `../Endhosts` and `../PrintQueue_Tofino`.

The code is tested under `Python3.8` and `Python 3.9`.
Run `pip3 -m install -r requirements.txt` to install dependencies.

## Run Test

The `Comparison` function in `GroundTruth.py` compares the diagnosis accuracy of time windows with related works. 
You can [download]() the pre-collected binaries to reproduce the results of the paper.
Folder `TW_RAW` stores the binary files of TW registers and INT data.
Folder `QM_RAW` stores the binary files of QM registers.