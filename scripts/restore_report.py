import json

transcript_path = r'C:\Users\MSI\.gemini\antigravity\brain\bbae1388-beef-444c-8a3f-a4aa7373bf90\.system_generated\logs\transcript_full.jsonl'
target_file_1 = r'c:\Users\MSI\Desktop\Final Market Pulse\docs\assignment\MARKET_PULSE_GLOBAL_REPORT_VI.md'
target_file_2 = r'C:\Users\MSI\.gemini\antigravity\brain\153c24cf-a8d3-420a-b1fa-e22a24571fa9\MARKET_PULSE_GLOBAL_REPORT_VI.md'

found = False
with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        tool_calls = data.get('tool_calls', [])
        for tc in tool_calls:
            if tc.get('name') == 'write_to_file':
                args = tc.get('args', {})
                target = args.get('TargetFile', '')
                if 'MARKET_PULSE_GLOBAL_REPORT_VI.md' in target:
                    content = args.get('CodeContent', '')
                    if isinstance(content, str) and content.startswith('" ) and content.endswith( \'):
 content = json.loads(content)
 with open(target_file_1, 'w', encoding='utf-8') as out1:
 out1.write(content)
 with open(target_file_2, 'w', encoding='utf-8') as out2:
 out2.write(content)
 print(f'Successfully restored {len(content.splitlines())} lines and {len(content.encode(\utf-8\))} bytes.')
 found = True
 break
 if found:
 break
