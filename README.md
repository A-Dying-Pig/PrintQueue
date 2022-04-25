# PrintQueue

The repository implements queue measurement techniques proposed in the paper entitled:

> [PrintQueue: Performance Diagnosis via Queue Measurement in the Data Plane]().
> **Yiran Lei, Liangcheng Yu, Vincent Liu, Mingwei Xu**. SIGCOMM'22.

Please find more information about the paper [here]().

## Architecture of the repository
The repository consists of three parts:
*  `AnalysisProgram`: process the register values polled from switches and execute queries.
*  `PrintQueue_Tofino`: PrintQueue's *P4<sub>14</sub>* data plane code and *C* control plane code running at [Intel Tofino](https://www.intel.com/content/www/us/en/products/network-io/programmable-ethernet-switch/tofino-series.html) ASIC.
*  `EndHosts`: send or receive packets on end hosts.

Detail is listed in each folder.

## Contact
Please raise [issues](https://github.com/A-Dying-Pig/PrintQueue/issues) if you have any questions or doubts about the code.
Feel free to contact via email leiyr20 [at] mails [dot] tsinghua [dot] cn.