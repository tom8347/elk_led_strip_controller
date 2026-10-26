{
  description = "PC-side controller for an ELK-BLEDDM / ELK-BLEDOM Bluetooth LED strip";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    python = pkgs.python3;

    elkbleddm = python.pkgs.buildPythonApplication {
      pname = "elkbleddm";
      version = "0.2.0";
      pyproject = true;
      src = ./.;

      build-system = [ python.pkgs.setuptools ];
      dependencies = [ python.pkgs.bleak ];
      nativeCheckInputs = [ python.pkgs.pytest ];
      nativeBuildInputs = [ pkgs.makeWrapper ];

      checkPhase = ''
        runHook preCheck
        pytest -q
        runHook postCheck
      '';

      # Screen sync shells out to wf-recorder; keep it in the app's PATH so
      # the installed `elk` works without relying on the user's environment.
      postFixup = ''
        wrapProgram $out/bin/elk \
          --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.wf-recorder pkgs.grim ]}
      '';

      meta = {
        description = "Control ELK-BLEDDM / ELK-BLEDOM BLE LED strips";
        mainProgram = "elk";
        platforms = pkgs.lib.platforms.linux;
      };
    };
  in
  {
    packages.${system} = {
      default = elkbleddm;
      elkbleddm = elkbleddm;
    };

    apps.${system}.default = {
      type = "app";
      program = "${elkbleddm}/bin/elk";
      meta.description = "Control an ELK-BLEDDM / ELK-BLEDOM BLE LED strip";
    };

    checks.${system}.default = elkbleddm;

    devShells.${system}.default = pkgs.mkShell {
      packages = [
        python
        python.pkgs.bleak
        python.pkgs.pytest
        pkgs.bluez
        pkgs.wireshark-cli
        pkgs.wf-recorder
        pkgs.grim
      ];

      shellHook = ''
        export PATH="$PWD:$PATH"
        echo "ELK LED strip dev environment loaded"
        python --version
        python -c 'import importlib.metadata as m; print("bleak", m.version("bleak"))'
        echo "bluetoothctl: $(command -v bluetoothctl)"
        echo "btmon:        $(command -v btmon)"
        echo "tshark:       $(command -v tshark)"
        echo "run the CLI with: elk ...   (or: nix run . -- ...)"
      '';
    };
  };
}
