# OLD (Fails on Py 3.12)
parser.add_argument("--url", env_var="SYNC_URL", help="API URL (env: SYNC_URL)")

# NEW (Compatible with Py 3.12+)
import os
parser.add_argument(
    "--url", 
    dest="url", 
    default=os.getenv("SYNC_URL"), 
    help="API URL (env: SYNC_URL)"
)
