# Copyright (c) 2025, Mahmoud and contributors
# For license information, please see license.txt

import frappe
from frappe import msgprint, _
from frappe.model.document import Document
from frappe.utils import flt, cstr, nowdate, comma_and


class ContractCheque(Document):
	def before_submit(self,update_modified=False):
		self.cheque_status="Issued"
		#self.save()
		#frappe.db.commit()		
		#self.set_status("Issued")

	def on_update(self,update_modified=False):
		self.set_status(self.cheque_status)

	def before_update_after_submit(self):
		self.set_status(self.cheque_status)

	def set_status(self, cheque_status=None):
		cont_revenue_acc = frappe.db.get_value("Company", self.company, "contract_revenue_account")
		if not cont_revenue_acc:
			frappe.throw(_("Contract Revenue Account not defined in the company setup page"))
		
		cont_int_dept_acc = frappe.db.get_value("Company", self.company, "contract_ntermediate_contract_debtors_account")
		if not cont_int_dept_acc:
			frappe.throw(_("Intermediate Contract Debtors Account not defined in the company setup page"))

		cheques_under_coll = frappe.db.get_value("Company", self.company, "contract_cheques_under_collection_account")
		if not cheques_under_coll:
			frappe.throw(_("Contract Cheques Under Collection Account not defined in the company setup page"))


		old_cheque_status = None
		party_type=None
		party=None
		party_type2=None
		party2=None

		if not self.is_new():
			try:
				old_doc = self.get_doc_before_save()
				old_cheque_status = old_doc.cheque_status
			except:
				pass
		
		if old_cheque_status:
			print ("old_cheque_status>>>>>>>>",old_cheque_status)

		if cheque_status == "Draft" and self.docstatus == 1:
			frappe.throw(_("Can't make it Draft after Issued"))

		
		if cheque_status == "Issued":
			# if old_cheque_status != "Draft" and self.docstatus == 1:
			# 	frappe.throw(_("Issued should be after Draft only"))

			if self.docstatus == 0: #and self.cheque_type == "Receivable":
				self.submit()
			
			#TODO Create GL entry
			####################################
			####################################
			if not self.issued_journal_entry :
				if self.deposit_account != cheques_under_coll:
					party_type2 = self.party_type
					party2 = self.party

				jv_name = self.make_journal_entry(self.deposit_account , cont_int_dept_acc, self.cheque_amount, self.posting_date, party_type=party_type, party=party, party_type2=party_type2, party2=party2,cost_center=None, 
						save=True, submit=True)
				frappe.db.set_value('Contract Cheque', self.name, 'issued_journal_entry', jv_name)

			frappe.db.set_value('Contract Cheque', self.name, 'cheque_status', 'Issued')#,update_modified=False)
			if self.deposit_account != cheques_under_coll:
				frappe.db.set_value('Contract Cheque', self.name, 'ignore_deducted_gl_entry', True)#,update_modified=False)

			
			frappe.db.commit()
			self.reload()

		if cheque_status == "Deducted":
			if old_cheque_status != "Issued" :
				frappe.throw(_("Deducted should be after Issued only"))			

			#TODO Create GL entry
			####################################
			if not self.ignore_deducted_gl_entry :
				if not self.collection_account:
					frappe.throw(_("Collection Account not Selected"))
					
				party_type2 = self.party_type
				party2 = self.party
				jv_name = self.make_journal_entry(self.collection_account, cheques_under_coll, self.cheque_amount, self.posting_date, party_type=party_type, party=party,party_type2=party_type2, party2=party2, cost_center=None, 
						save=True, submit=True)
				
				# Log a custom activity
				usr_message = _("Journal Entry {0} created").format(comma_and(jv_name))
				self.add_comment("Info", usr_message)	

		if cheque_status == "Cancelled":
			if old_cheque_status != "Issued" :
				frappe.throw(_("Cancelled should be after Issued only"))			

			#TODO Create GL entry 
			####################################
			jv_name = self.make_journal_entry(cont_int_dept_acc, cheques_under_coll, self.cheque_amount, self.posting_date, party_type=None, party=None, cost_center=None, 
					save=True, submit=True)
			
			# Log a custom activity
			usr_message = _("Journal Entry {0} created").format(comma_and(jv_name))
			self.add_comment("Info", usr_message)	

	def make_journal_entry(self, account1, account2, amount, posting_date=None, party_type=None, party=None, party_type2=None, party2=None, cost_center=None, 
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
				"party_type": party_type2 ,
				"party": party2 ,
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
		
		return jv.name						