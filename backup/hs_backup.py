name: Sauvegarde nocturne de la base

on:
  schedule:
    - cron: "17 2 * * *"      # tous les jours à 02h17 UTC (03h17 / 04h17 en France)
  workflow_dispatch:           # bouton « Run workflow » pour lancer une sauvegarde à la main

permissions:
  contents: read

jobs:
  sauvegarde:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
      BACKUP_PASSPHRASE: ${{ secrets.BACKUP_PASSPHRASE }}
    steps:
      - name: Récupérer le script de sauvegarde
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          git clone --depth 1 "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" depot
          cp depot/backup/hs_backup.py .

      - name: Installer la dépendance de chiffrement
        run: python3 -m pip install --quiet cryptography

      - name: Exporter et chiffrer la base
        run: python3 hs_backup.py exporter --sortie "handstats_$(date -u +%Y%m%d_%H%M%S).hsbk"

      - name: Conserver la sauvegarde (60 jours)
        uses: actions/upload-artifact@v7
        with:
          name: sauvegarde-handstats-${{ github.run_number }}
          path: handstats_*.hsbk
          retention-days: 60
          if-no-files-found: error
