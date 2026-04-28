# Create the environment
conda create -n duckchess python=3.12 -y
conda activate duckchess

# Install PyQt via Conda (handles system-level graphics drivers better)
conda install pyqt -c conda-forge -y
conda install -c conda-forge ndcctools

# Install the rest via your requirements file
pip install -r requirements.txt

# Update a new pip install
pip list --format=freeze > requirements.txt

# Taskvine
## Start manager
python3 quickstart.py

## Start 1 local worker
vine_worker localhost 9123

## Submit 10 workers to HTCondor Pool
vine_submit_workers -T condor MACHINENAME 9123 10