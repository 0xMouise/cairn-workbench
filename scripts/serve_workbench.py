import os
from pathlib import Path
import uvicorn
from cairn.workbench.app import create_app

if __name__ == "__main__":
    uvicorn.run(
        create_app(
            Path(
                os.environ.get(
                    "CAIRN_WORKBENCH_DATA",
                    str(Path.home() / ".local/share/cairn-workbench"),
                )
            )
        ),
        host="127.0.0.1",
        port=int(os.environ.get("CAIRN_WORKBENCH_PORT", "18100")),
        access_log=False,
    )
