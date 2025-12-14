# Copyright (c) 2025, Mahmoud and contributors
# For license information, please see license.txt

import frappe
from frappe import msgprint, _
from frappe.model.document import Document
from frappe.utils import flt, cstr, nowdate, comma_and


class FinishingContract(Document):
	def validate(self):
		print("Saving ...........")


	def on_submit(self,update_modified=False):
		cont_revenue_acc = frappe.db.get_value("Company", self.company, "contract_revenue_account")
		if not cont_revenue_acc:
			frappe.throw(_("Contract Revenue Account not defined in the company setup page"))
		
		cont_int_dept_acc = frappe.db.get_value("Company", self.company, "contract_ntermediate_contract_debtors_account")
		if not cont_int_dept_acc:
			frappe.throw(_("Intermediate Contract Debtors Account not defined in the company setup page"))
				
		# contr_chqu_uc_acc = frappe.db.get_value("Company", self.company, "contract_cheques_under_collection_account")
		# if not contr_chqu_uc_acc:
		# 	frappe.throw(_("Contract Cheques Under Collection Account not defined in the company setup page"))

		usr_message = self.make_journal_entry(cont_int_dept_acc, cont_revenue_acc, self.total_amount, self.posting_date, party_type=None, party=None, cost_center=None, 
				save=True, submit=True)
		
		# Log a custom activity
		self.add_comment("Info", usr_message)
		#self.add_comment("Comment", usr_message)
		# frappe.log_activity(
		# 	document_type="Finishing Contract",  # Optional: Link to a specific DocType
		# 	document_name=self.name,           # Optional: Link to a specific document
		# 	subject= usr_message, # The main subject of the activity
		# 	reference_doctype="User",          # Optional: Reference another DocType
		# 	reference_name=frappe.session.user # Optional: Reference a specific document name (e.g., the current user)
		# )

		so_ = frappe.get_doc('Sales Order', self.sales_order)
		pyments = so_.payment_schedule
		cheque_no_loop=0
		for pymt in pyments:
			cheque_no_loop = cheque_no_loop +1
			new_chq = frappe.new_doc("Contract Cheque")
			new_chq.finishing_contract = self
			new_chq.cheque_no = cheque_no_loop
			new_chq.company = self.company
			new_chq.cheque_date = pymt.due_date
			new_chq.posting_date = self.posting_date or nowdate()
			new_chq.project = self.project
			new_chq.cheque_amount = pymt.payment_amount
			new_chq.cheque_status = "Draft"

			new_chq.insert()

			#print (str(pymt.due_date),str(pymt.payment_amount))

		frappe.db.commit()

	def make_journal_entry(self, account1, account2, amount, posting_date=None, party_type=None, party=None, cost_center=None, 
							save=True, submit=False):
		jv = frappe.new_doc("Journal Entry")
		jv.posting_date = posting_date or nowdate()
		jv.company = self.company
		jv.user_remark = self.remarks or self.name
		jv.multi_currency = 0
		jv.set("accounts", [
			{
				"account": account1,
				"party_type": party_type ,
				"party": party ,
				"cost_center": cost_center,
				"project": self.project,
				"debit_in_account_currency": amount if amount > 0 else 0,
				"credit_in_account_currency": abs(amount) if amount < 0 else 0
			}, {
				"account": account2,
				"party_type": party_type ,
				"party": party ,
				"cost_center": cost_center,
				"project": self.project,
				"credit_in_account_currency": amount if amount > 0 else 0,
				"debit_in_account_currency": abs(amount) if amount < 0 else 0
			}
		])
		if save or submit:
			jv.insert(ignore_permissions=True)

			if submit:
				jv.submit()

		frappe.db.commit()
		message = """<a href="%s" target="_blank">%s</a>""" % (frappe.utils.get_url_to_form("Journal Entry", jv.name), jv.name)
		usr_message= _("Journal Entry {0} created").format(comma_and(message))
		msgprint(usr_message)
		#message = _("Journal Entry {0} created").format(comma_and(message))
		
		return usr_message
