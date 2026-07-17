import pickle
import os

val_dir = 'experiments/outputs/TwoStream/isign_s2t/validation/'
if not os.path.exists(val_dir):
    print("Validation directory doesn't exist yet:", val_dir)
else:
    steps = sorted([d for d in os.listdir(val_dir) if d.startswith('step_')])
    if not steps:
        print('No validation folders found!')
    else:
        latest_step = steps[-1]
        pkl_path = os.path.join(val_dir, latest_step, 'results.pkl')
        print('Loading:', pkl_path)
        if os.path.exists(pkl_path):
            with open(pkl_path, 'rb') as f:
                results = pickle.load(f)
            
            # Print the first 15 predictions
            count = 0
            for uid, data in results.items():
                if 'txt_hyp' in data:
                    print(f'Sample {count+1}:')
                    print(f'  Hyp: "{data["txt_hyp"]}"')
                    print(f'  Ref: "{data["txt_ref"]}"')
                    print('-' * 40)
                    count += 1
                    if count >= 15:
                        break
        else:
            print("results.pkl not found at:", pkl_path)
