import frappe

def set_account_root_type(doc, method):
	"""
	Force specific root_types based on Account Number (or the numeric prefix of Account Name).
	Only applies to 'Asset' or 'Liability' Lebanese chart of accounts schema.
	"""
	if not doc.account_number and not doc.account_name:
		return
		
	# Determine the numeric prefix. Try account_number first, fallback to account_name.
	identifier = str(doc.account_number or doc.account_name).strip()
	
	# Extract only the leading digits
	prefix = ""
	for char in identifier:
		if char.isdigit():
			prefix += char
		else:
			break
			
	if not prefix:
		return
		
	# Mapping rules: Longest match first if applicable.
	# We'll check the prefix string directly.
	
	asset_prefixes = ["41", "421", "438", "459", "468", "469", "47"]
	liability_prefixes = [
		"40", "428", "431", "44", "451", "453", "461", "463", "465", "48", "49"
	]
	
	# To ensure we match the most specific rule (e.g., "47" vs "471"), we check exact starts_with 
	# starting from the longest possible prefixes downward if needed. 
	# For our list, standard `startswith` iteration from longest to shortest is best.
	
	all_prefixes = asset_prefixes + liability_prefixes
	all_prefixes.sort(key=len, reverse=True) # Check 3 digit combinations first
	
	for p in all_prefixes:
		if prefix.startswith(p):
			if p in asset_prefixes:
				doc.root_type = "Asset"
			else:
				doc.root_type = "Liability"
			break
