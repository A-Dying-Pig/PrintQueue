# PrintQueue's Analysis Program
The analysis program consists of three parts:
* `TimeWindows.py`: read binary files of register values and execute queries.
* `GroundTruth.py`: read binary files of PrintQueue INT data and return ground truth.
* `QueueMonitor.py`: read binary files of register values and construct the queue stack.

The layout of binary files can be found in `../Endhosts` and `../PrintQueue_Tofino`.

Run `pip3 -m install -r requirements.txt` to install dependencies.

## Run Test

The `Comparison` function in `GroundTruth.py` compares the diagnosis accuracy of time windows with related works.
The program samples a number of packets encountering various queue depth. 
Do precision and recall (P&R) for the direct culprits of the sampled packets.

The `DataPlaneQuery` function in `GroundTruth.py` returns the P&R accuracy when data plane query is triggered.

The `Timer` function in `GroundTruth.py` gets query-per-second (QPS) of asynchronous queries.