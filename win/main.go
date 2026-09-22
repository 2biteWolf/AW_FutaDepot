package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"unsafe"
)

func msg(title, text string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	proc := user32.NewProc("MessageBoxW")
	t, _ := syscall.UTF16PtrFromString(title)
	b, _ := syscall.UTF16PtrFromString(text)
	proc.Call(0, uintptr(unsafe.Pointer(b)), uintptr(unsafe.Pointer(t)), 0x10)
}

func look(name string) string {
	p, err := exec.LookPath(name)
	if err != nil {
		return ""
	}
	return p
}

func findPython() (string, []string) {
	if p := look("pyw"); p != "" {
		return p, []string{"-3"}
	}
	if p := look("pythonw"); p != "" {
		return p, nil
	}
	if p := look("py"); p != "" {
		return p, []string{"-3"}
	}
	if p := look("python"); p != "" {
		return p, nil
	}
	if p := look("python3"); p != "" {
		return p, nil
	}
	return "", nil
}

func main() {
	exe, err := os.Executable()
	if err != nil {
		msg("AW_FutaDepot", err.Error())
		return
	}
	dir := filepath.Dir(exe)
	script := filepath.Join(dir, "ui.py")
	if _, err := os.Stat(script); err != nil {
		msg("AW_FutaDepot", "ui.py missing next to the exe")
		return
	}
	py, prefix := findPython()
	if py == "" {
		msg("AW_FutaDepot", "Python 3 with Tcl/Tk is required.")
		return
	}
	args := append(append([]string{}, prefix...), script)
	cmd := exec.Command(py, args...)
	cmd.Dir = dir
	if err := cmd.Run(); err != nil {
		msg("AW_FutaDepot", err.Error())
	}
}
