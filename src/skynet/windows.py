from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from collections.abc import Callable


class WindowsError(RuntimeError):
    pass


Runner = Callable[[str, int], str]


class WindowsController:
    """Native Windows automation using built-in PowerShell/.NET APIs.

    UI Automation is preferred over blind coordinate clicking. Write/action
    methods are expected to be permission-gated by ToolBus.
    """

    def __init__(self, workspace: Path, runner: Runner | None = None) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._runner = runner or self._run_ps

    @staticmethod
    def _run_ps(script: str, timeout: int = 30) -> str:
        if os.name != "nt":
            raise WindowsError("Windows automation is available only on Windows")
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=max(1, min(timeout, 120)),
            shell=False,
        )
        output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if completed.returncode != 0:
            raise WindowsError(output or f"PowerShell failed with exit code {completed.returncode}")
        return output

    @staticmethod
    def _ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def list_windows(self) -> str:
        script = r"""
$items = Get-Process |
  Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle } |
  Select-Object Id, ProcessName, MainWindowTitle
$items | ConvertTo-Json -Compress
"""
        return self._runner(script, 20) or "[]"

    def accessibility_snapshot(self, max_nodes: int = 100) -> str:
        max_nodes = max(1, min(int(max_nodes), 250))
        script = rf"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::FocusedElement
if ($null -eq $root) {{ $root = [System.Windows.Automation.AutomationElement]::RootElement }}
$queue = New-Object 'System.Collections.Generic.Queue[System.Windows.Automation.AutomationElement]'
$queue.Enqueue($root)
$out = @()
while ($queue.Count -gt 0 -and $out.Count -lt {max_nodes}) {{
  $e = $queue.Dequeue()
  try {{
    $out += [pscustomobject]@{{
      name = $e.Current.Name
      control_type = $e.Current.ControlType.ProgrammaticName
      automation_id = $e.Current.AutomationId
      enabled = $e.Current.IsEnabled
      offscreen = $e.Current.IsOffscreen
    }}
    $children = $e.FindAll(
      [System.Windows.Automation.TreeScope]::Children,
      [System.Windows.Automation.Condition]::TrueCondition
    )
    foreach ($c in $children) {{
      if ($queue.Count + $out.Count -ge {max_nodes * 2}) {{ break }}
      $queue.Enqueue($c)
    }}
  }} catch {{}}
}}
$out | ConvertTo-Json -Compress -Depth 4
"""
        return self._runner(script, 30) or "[]"

    def focus_window(self, title_contains: str) -> str:
        title = self._ps_quote(title_contains)
        script = rf"""
$target = Get-Process |
  Where-Object {{ $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like ('*' + {title} + '*') }} |
  Select-Object -First 1
if ($null -eq $target) {{ throw 'No matching window found' }}
$ws = New-Object -ComObject WScript.Shell
if (-not $ws.AppActivate($target.Id)) {{ throw 'Could not activate matching window' }}
"Focused: $($target.MainWindowTitle)"
"""
        return self._runner(script, 20)

    def invoke_element(self, name: str) -> str:
        target = self._ps_quote(name)
        script = rf"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::FocusedElement
if ($null -eq $root) {{ throw 'No focused UI element' }}
$window = $root
while ($null -ne $window -and $window.Current.ControlType -ne [System.Windows.Automation.ControlType]::Window) {{
  $window = [System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($window)
}}
if ($null -eq $window) {{ $window = [System.Windows.Automation.AutomationElement]::RootElement }}
$condition = [System.Windows.Automation.PropertyCondition]::new(
  [System.Windows.Automation.AutomationElement]::NameProperty,
  {target}
)
$element = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
if ($null -eq $element) {{ throw 'UI element not found' }}
$pattern = $null
if ($element.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {{
  $pattern.Invoke()
  "Invoked: " + $element.Current.Name
}} else {{
  throw 'Element does not expose InvokePattern'
}}
"""
        return self._runner(script, 30)

    def type_text(self, text: str) -> str:
        encoded = text.encode("utf-16le").hex()
        script = rf"""
Add-Type -AssemblyName System.Windows.Forms
$hex = '{encoded}'
$bytes = New-Object byte[] ($hex.Length / 2)
for ($i = 0; $i -lt $bytes.Length; $i++) {{
  $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
}}
$text = [Text.Encoding]::Unicode.GetString($bytes)
Set-Clipboard -Value $text
[System.Windows.Forms.SendKeys]::SendWait('^v')
"Typed {len(text)} characters via clipboard paste"
"""
        return self._runner(script, 20)

    def screenshot(self, relative_path: str = "screenshots/latest.png") -> str:
        path = (self.workspace / relative_path).resolve()
        try:
            path.relative_to(self.workspace)
        except ValueError as exc:
            raise WindowsError("Screenshot path escapes workspace") from exc
        if path.suffix.lower() != ".png":
            raise WindowsError("Screenshot path must end in .png")
        path.parent.mkdir(parents=True, exist_ok=True)
        quoted = self._ps_quote(str(path))
        script = rf"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
try {{
  $g.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bounds.Size)
  $bmp.Save({quoted}, [System.Drawing.Imaging.ImageFormat]::Png)
}} finally {{
  $g.Dispose()
  $bmp.Dispose()
}}
"Saved screenshot"
"""
        self._runner(script, 30)
        return str(path)
