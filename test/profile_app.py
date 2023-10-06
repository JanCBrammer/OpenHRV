import cProfile
from test.app import main
import subprocess

cProfile.run("main()", "openhrv.profile")
subprocess.run(["snakeviz", "openhrv.profile"], check=True)
