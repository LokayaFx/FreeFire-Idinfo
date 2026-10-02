"""Opt-in live diagnostic. Prints metadata only; never tokens or player data."""
import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from protocol import UpstreamError

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--regions', nargs='+', default=['BD'])
parser.add_argument('--uid', help='Optional authorized test player UID; not written to output')
parser.add_argument('--self-lookup', action='store_true',
                    help='Look up the guest account identified by its own login token')
args = parser.parse_args()
if args.uid and args.self_lookup:
    parser.error('Use either --uid or --self-lookup, not both')
regions = [app.normalize_region(region) for region in args.regions]


def own_account_uid(bearer_token):
    payload = bearer_token.removeprefix('Bearer ').split('.')[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    uid = str(claims['account_id'])
    return app.validate_uid(uid)

async def run():
    failed = False
    for region in regions:
        result = {'region': region, 'protocol': app.RELEASEVERSION}
        try:
            await app.create_jwt(region)
            info = app.cached_tokens[region]
            result.update(login='ok', lock_region=info['region'], server_host=urlsplit(info['server_url']).hostname)
            lookup_uid = own_account_uid(info['token']) if args.self_lookup else args.uid
            if lookup_uid:
                data = await app.GetAccountInformation(app.validate_uid(lookup_uid), '7', region, '/GetPlayerPersonalShow')
                result['player_found'] = bool(data.get('basicInfo', {}).get('nickname'))
                result['sections'] = sorted(data)
                failed |= not result['player_found']
        except UpstreamError as exc:
            failed = True
            result.update(error_code=exc.code, message=str(exc))
        except Exception as exc:
            failed = True
            result.update(error_code='DIAGNOSTIC_FAILED', error_type=type(exc).__name__)
        print(json.dumps(result), flush=True)
    return 1 if failed else 0

if __name__ == '__main__':
    raise SystemExit(asyncio.run(run()))
