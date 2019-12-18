# Tutorial

## Setup
The recommended way to setup your computer for running Inimotif is to install the official distribution of Python 3.7. You can download the official Python 3.7 distribution [here](https://www.python.org/downloads/release/python-375). Once you've installed Python, open the terminal/prompt and enter the following command:
```
pip install -r requirements.txt
```
This will install the required python packages that Inimotif needs to run. Note that Inimotif may work for versions of Python 3 prior to 3.7, but this is untested. For Mac you may need to update Tcl/Tk to use the GUI for versions of Python prior to 3.7.2. See [here](https://www.python.org/download/mac/tcltk/) for more information.
<br/>
<br/>
Alternatively, you can also run Inimotif using [Anaconda](https://www.anaconda.com/distribution/). To setup a conda environment and install the requirements:
```
conda create -y --name inimotif python==3.7
conda install -fyq --name inimotif -c conda-forge --file requirements.txt
conda activate inimotif
```

## Running
Open the GUI by opening the directory containing the python files in a terminal, and run the inimotif_gui.py using python3.
```bash
$ python3 inimotif_gui.py
```
Select from one of the three options: ChP-seq, SELEX-seq, or Masker.

### ChIP-seq
For ChIP-seq data, you will be promted to enter: Identifier (name of output file), Input file (data to be analysed), Output directory (where should results be written), Minimum and Maximum Kmer length (kmers within the range of these variables will be scanned).

![ChIP form entry](https://https://github.com/chengl7/IniMotif/new/master/tutorial/screenshots/ChIPexampleGUI)

### SELEX-seq
For SELEX-seq data, you will be promted to enter: Identifier, Minimum SELEX round number, Maximum SELEX round number, Input files (for in the range of min and max round number), Output directory, Minimum and Maximum Kmer length.

![SELEX form entry](https://https://github.com/chengl7/IniMotif/new/master/tutorial/screenshots/SELEXexampleGUI)

### Masker
Masker will ask for an input file, and the output file name with location. Clicking the "Add Pattern" button will produce a new input row where the masks can be specified. Inputs for a pattern require: Type (repeat or motif), Reverse compliment (mask revcom of sequence), Sequence (to be masked), and depending on the type Number of minimum repeats, or Number of maximum mutations.

![Masker form entry](https://https://github.com/chengl7/IniMotif/new/master/tutorial/screenshots/MaskerexampleGUI)


## Sub tabs

Both SELEX and ChIP seq tabs have the subtabs:

### Motif scan

The required inputs include: input and output directory, and up to n consensus sequence(s) with how many mutations, and a reverse compliment option.

![Motif scan form entry](https://https://github.com/chengl7/IniMotif/new/master/tutorial/screenshots/MotifScanexampleGUI)

### Top kmer

The Top kmer tab only requires 2 inputs: the prepoc.pickle file produced from an analysis (can be found in the rXkX directories of the analysis output directory), and the number of top kmers to be displayed.

![Top kmers form entry](https://https://github.com/chengl7/IniMotif/new/master/tutorial/screenshots/TopKmerexampleGUI)

### Kmer query

Similar to the Top kmer tab, the Kmer query tab on requires two entries: a preproc.pickle file, and input kmers (one per line).

![Top kmers form entry](https://https://github.com/chengl7/IniMotif/new/master/tutorial/screenshots/KmerQueryexampleGUI)

