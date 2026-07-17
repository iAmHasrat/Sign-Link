import os, time, re

# Dynamically locate log path relative to this script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
log_path = os.path.join(script_dir, "experiments/outputs/TwoStream/isign_s2t/train.rank0.log")

def parse_logs():
    if not os.path.exists(log_path):
        return None
    
    with open(log_path, "r") as f:
        lines = f.readlines()
        
    runs = {}
    current_step = None
    current_epoch = "0"
    
    # Regex patterns
    step_pat = re.compile(r"Evaluation global step=(\d+)")
    epoch_pat = re.compile(r"Evaluation epoch=(\d+)")
    loss_pat = re.compile(r"translation_loss Average:([\d\.]+)")
    bleu_pat = re.compile(r"bleu4 ([\d\.]+)")
    rouge_pat = re.compile(r"ROUGE: ([\d\.]+)")
    chrf_pat = re.compile(r"ChrF: ([\d\.]+)")
    best_pat = re.compile(r"best_score=([\d\.]+)")
    
    epoch_start_pat = re.compile(r"Epoch (\d+), Training examples")

    for line in lines:
        m_est = epoch_start_pat.search(line)
        if m_est:
            current_epoch = m_est.group(1)
            
        m_step = step_pat.search(line)
        if m_step:
            current_step = int(m_step.group(1))
            runs[current_step] = {"epoch": current_epoch}
            continue
            
        m_epoch_val = epoch_pat.search(line)
        if m_epoch_val:
            current_step = f"Epoch {m_epoch_val.group(1)}"
            runs[current_step] = {"epoch": m_epoch_val.group(1)}
            continue
            
        if current_step is not None and current_step in runs:
            m_loss = loss_pat.search(line)
            if m_loss:
                runs[current_step]["loss"] = m_loss.group(1)
            m_bleu = bleu_pat.search(line)
            if m_bleu:
                runs[current_step]["bleu4"] = m_bleu.group(1)
            m_rouge = rouge_pat.search(line)
            if m_rouge:
                runs[current_step]["rouge"] = m_rouge.group(1)
            m_chrf = chrf_pat.search(line)
            if m_chrf:
                runs[current_step]["chrf"] = m_chrf.group(1)
            m_best = best_pat.search(line)
            if m_best:
                runs[current_step]["best"] = m_best.group(1)
                
    return runs

def draw_dashboard():
    os.system('clear' if os.name == 'posix' else 'cls')
    runs = parse_logs()
    
    print("=" * 70)
    print("            iSIGN S2T TRAINING MONITOR DASHBOARD")
    print("=" * 70)
    
    if not runs:
        print(f"Waiting for log file: {log_path} to populate...")
        return
        
    print(f"Source Log: {log_path}")
    print("-" * 70)
    print(f"{'Step/Eval':<12} | {'Epoch':<6} | {'Val Loss':<10} | {'BLEU-4':<8} | {'ROUGE':<8} | {'ChrF':<8}")
    print("-" * 70)
    
    best_bleu = 0.0
    for step in sorted(runs.keys(), key=lambda x: int(x) if isinstance(x, int) else 999999):
        info = runs[step]
        epoch = info.get("epoch", "-")
        loss = info.get("loss", "-")
        bleu4 = info.get("bleu4", "-")
        rouge = info.get("rouge", "-")
        chrf = info.get("chrf", "-")
        
        if bleu4 != "-":
            best_bleu = max(best_bleu, float(bleu4))
            
        print(f"{str(step):<12} | {epoch:<6} | {loss:<10} | {bleu4:<8} | {rouge:<8} | {chrf:<8}")
        
    print("-" * 70)
    print(f"Best BLEU-4 achieved: {best_bleu:.2f}")
    print("=" * 70)
    print("Updating every 10 seconds... (Press Ctrl+C to exit)")

while True:
    try:
        draw_dashboard()
        time.sleep(10)
    except KeyboardInterrupt:
        break
