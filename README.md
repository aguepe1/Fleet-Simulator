# Fleet-Simulator
Optimize your railway reserve fleet with this Monte Carlo simulator. Built with Python &amp; Tkinter, it uses Weibull distributions for realistic failure modeling to determine the minimum fleet size required to guarantee a specific service level, moving beyond simple percentage-based rules.
Railway Fleet Optimization Simulator
A dynamic Monte Carlo simulation tool built with Python to determine the optimal reserve fleet size for railway operations. This application moves beyond static, percentage-based rules by using stochastic modeling to find the minimum number of trains required to meet a specific service level target, enabling data-driven investment and operational decisions.

Overview
Sizing a reserve fleet is a critical trade-off between Capital Expenditure (CapEx) and service reliability. An oversized reserve fleet leads to millions in underutilized assets, while an undersized one risks service failures, penalty fees, and customer dissatisfaction.

This simulator tackles the problem by reframing the core question: instead of asking "How many reserve trains do we need for our existing fleet?", we ask "To guarantee our target service level, what is the minimum fleet size required?"

The tool iteratively simulates fleet operations, adding one reserve train at a time and running thousands of annual simulations at each step until the desired service level is achieved, thus identifying the true minimum required fleet.

Features
Stochastic Simulation: Utilizes the Monte Carlo method to model uncertainty in failures and repairs.

Realistic Failure Modeling: Implements the Weibull distribution to simulate age-based wear-out failures, where older assets are more likely to fail.

Interactive GUI: A user-friendly interface built with Tkinter allows for easy parameter adjustment and real-time feedback.

Dynamic Parameter Validation: The interface provides instant visual feedback (color-coded fields) and disables the simulation run if any parameter is invalid, preventing user error.

Flexible Maintenance Policies: A structured UI to define custom probability distributions for the number of trains entering scheduled maintenance.

Live Previews: Instantly visualize the shape of failure and repair distributions as you adjust their parameters, before running the full simulation.

Detailed Outputs: Generates comprehensive logs, a historical plot of the optimization search, and final distribution graphs.

Core Technical Concepts
This simulator is built on several key statistical and engineering principles:

1. Monte Carlo Simulation
Instead of a single deterministic calculation, the application runs thousands of iterations (or "virtual years"). In each iteration, every random variable is sampled from its defined statistical distribution.

A failure is determined by a random draw against the train's daily failure probability.

A repair or maintenance duration is a random draw from its discrete Weibull distribution.

The number of trains entering maintenance is a random draw from the user-defined probability mass function.

By aggregating the results of thousands of these independent annual simulations, we build a distribution of possible outcomes. This allows us to quantify risk and answer questions like, "What is the 95th percentile outcome?" or "What is the probability of falling below our service target?"

2. Weibull Distribution (Failure Modeling)
The time-to-failure of mechanical components is rarely constant. The Weibull distribution is used to model this reality. Its probability density function is controlled by two main parameters:

Shape parameter (k or 
beta): This determines the nature of the failure rate over time.

k < 1: Indicates early life failures (infant mortality).

k = 1: Constant failure rate (equivalent to the Exponential distribution).

k > 1: Increasing failure rate with age (models wear-out and aging), which is the most common scenario for mechanical assets like trains.

Scale parameter (
lambda or 
eta): This is the characteristic life of the asset.

This simulator uses the Weibull Hazard Rate Function to calculate the daily probability of failure for each train based on its "age" (days since its last major repair/maintenance). This creates a much more realistic simulation than assuming a constant failure rate.

3. Discrete Weibull Distribution (Repair & Maintenance Durations)
Since repair and maintenance times are measured in whole days, a discrete probability distribution is required. The simulator uses a discrete analog of the Weibull distribution to model these durations, providing flexibility in representing repair time variability.

Tech Stack
Language: Python 3

GUI: Tkinter (standard library)

Numerical & Scientific: NumPy, SciPy

Plotting: Matplotlib

Setup and Installation
Clone the repository:

Bash

git clone https://your-repository-url/fleet-simulator.git
cd fleet-simulator
Create and activate a virtual environment:

Bash

# For Windows
python -m venv .venv
.venv\Scripts\activate

# For macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
Install dependencies:
A requirements.txt file is included for easy setup.

Bash

pip install -r requirements.txt
(The requirements.txt should contain numpy, scipy, and matplotlib)

How to Use
Run the application:

Bash

python interfaz_simulador.py
Configure Parameters:

General Configuration: Set the number of required operational trains and the target service level.

Failure Parameters: Adjust the overall asset availability and the Weibull shape parameter (k) to model fleet aging.

Maintenance Policy: Add or remove rules to define the probability of a certain number of trains entering maintenance each day. The UI provides real-time validation to ensure the total probability is 100%.

Repair/Maintenance Duration: Define the mean duration and Weibull shape parameter for both unscheduled repairs and scheduled maintenance.

Hourly Requirements: Specify the minimum number of trains needed for each hour of the day.

Run Simulation:

The "Iniciar Búsqueda" button will be enabled only when all parameters are valid.

Click it to start the simulation. The log and history plot will update in real time.

Click the "Detener" button to interrupt the simulation at any time.

Analyze Results:

Log Tab: Shows a detailed, step-by-step log of the optimization process.

History Plot: Visualizes each simulation attempt, showing how the service level responds as more reserve trains are added. The final, optimal solution is marked with a vertical line.

Distribution Plots: Show the final, underlying statistical distributions used for the optimal configuration.

File Structure
interfaz_simulador.py: The frontend application. Contains all GUI code (Tkinter), user input handling, real-time validation, and plotting logic.

simulacion_flota.py: The backend simulation engine. Contains the core Monte Carlo simulation logic, statistical functions (Weibull, etc.), and the optimization algorithm.

Future Improvements
[ ] Implement cost analysis (CapEx of reserve trains vs. OpEx of service failures).

[ ] Allow saving and loading of parameter configurations to/from a file (e.g., JSON, YAML).

[ ] Add more complex maintenance triggers (e.g., condition-based or age-based).

[ ] Export simulation results and graphs to a PDF or CSV report.
