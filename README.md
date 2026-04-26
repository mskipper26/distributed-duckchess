# Create the environment
conda create -n duckchess python=3.12 -y
conda activate duckchess

# Install PyQt via Conda (handles system-level graphics drivers better)
conda install pyqt -c conda-forge -y

# Install the rest via your requirements file
pip install -r requirements.txt

# Update a new pip install
pip list --format=freeze > requirements.txt