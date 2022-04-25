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
The program samples a number of packets encoutering various queue depth. 
Calculate precision and recall of sampled packets under time windows and related works.

Download and unzip the pre-collected binaries to reproduce the results of the paper.
* Folder [TW_RAW](https://drive.google.com/file/d/1p0-YiI_CBbw4-bugU6NFfq25v4WF2tC-/view?usp=sharing) contains binaries comparing TW of different parameters `alpha_k_T` with related works.
