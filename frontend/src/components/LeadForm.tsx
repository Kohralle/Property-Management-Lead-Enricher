import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { personsApi, buildingsApi } from '../api/leads'
import type { Person, Building } from '../api/types'

interface Props {
  person?: Person
  onClose: () => void
}

const COUNTRIES = ['USA', 'Canada', 'UK', 'Australia', 'Other']

export default function LeadForm({ person, onClose }: Props) {
  const qc = useQueryClient()
  const isEdit = !!person

  const [name, setName] = useState(person?.name ?? '')
  const [email, setEmail] = useState(person?.email ?? '')
  const [company, setCompany] = useState(person?.company ?? '')
  const [buildingId, setBuildingId] = useState<number | null>(person?.building ?? null)
  const [showNewBuilding, setShowNewBuilding] = useState(false)
  const [bAddr, setBAddr] = useState('')
  const [bCity, setBCity] = useState('')
  const [bState, setBState] = useState('')
  const [bCountry, setBCountry] = useState('USA')
  const [error, setError] = useState('')

  const { data: buildings } = useQuery({
    queryKey: ['buildings'],
    queryFn: () => buildingsApi.list().then((r) => r.data.results),
  })

  const createBuilding = useMutation({
    mutationFn: (d: Omit<Building, 'id' | 'created_at' | 'updated_at'>) => buildingsApi.create(d),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['buildings'] }),
  })

  const savePerson = useMutation({
    mutationFn: (d: Parameters<typeof personsApi.create>[0]) =>
      isEdit ? personsApi.update(person!.id, d) : personsApi.create(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['persons'] })
      onClose()
    },
    onError: (e: any) => {
      setError(e.response?.data?.email?.[0] ?? 'Something went wrong.')
    },
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    let bid = buildingId

    if (showNewBuilding) {
      if (!bAddr || !bCity || !bState) {
        setError('Please fill in all building fields.')
        return
      }
      const res = await createBuilding.mutateAsync({ property_address: bAddr, city: bCity, state: bState, country: bCountry })
      bid = res.data.id
    }

    savePerson.mutate({ name, email, company, building: bid })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-apple-gray">Contact</p>
        <Field label="Full Name" value={name} onChange={setName} required />
        <Field label="Email" type="email" value={email} onChange={setEmail} required />
        <Field label="Company" value={company} onChange={setCompany} />
      </div>

      <div className="space-y-3 pt-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-apple-gray">Building</p>

        <div className="bg-apple-lightgray rounded-xl overflow-hidden divide-y divide-apple-separator">
          <label className="flex items-center gap-3 px-4 py-3 cursor-pointer">
            <input
              type="radio"
              name="building_mode"
              checked={!showNewBuilding && buildingId === null}
              onChange={() => { setShowNewBuilding(false); setBuildingId(null) }}
              className="accent-apple-blue"
            />
            <span className="text-[15px] text-gray-500">No building</span>
          </label>

          {buildings?.map((b) => (
            <label key={b.id} className="flex items-center gap-3 px-4 py-3 cursor-pointer">
              <input
                type="radio"
                name="building_mode"
                checked={!showNewBuilding && buildingId === b.id}
                onChange={() => { setShowNewBuilding(false); setBuildingId(b.id) }}
                className="accent-apple-blue"
              />
              <div>
                <p className="text-[15px] text-gray-900">{b.property_address}</p>
                <p className="text-[13px] text-apple-gray">{b.city}, {b.state}</p>
              </div>
            </label>
          ))}

          <label className="flex items-center gap-3 px-4 py-3 cursor-pointer">
            <input
              type="radio"
              name="building_mode"
              checked={showNewBuilding}
              onChange={() => { setShowNewBuilding(true); setBuildingId(null) }}
              className="accent-apple-blue"
            />
            <span className="text-[15px] text-apple-blue font-medium">Add new building…</span>
          </label>
        </div>

        {showNewBuilding && (
          <div className="space-y-3 pl-2 border-l-2 border-apple-blue">
            <Field label="Property Address" value={bAddr} onChange={setBAddr} required />
            <div className="grid grid-cols-2 gap-3">
              <Field label="City" value={bCity} onChange={setBCity} required />
              <Field label="State" value={bState} onChange={setBState} required />
            </div>
            <div>
              <label className="block text-[13px] text-apple-gray mb-1">Country</label>
              <select
                value={bCountry}
                onChange={(e) => setBCountry(e.target.value)}
                className="w-full bg-apple-lightgray rounded-xl px-4 py-2.5 text-[15px] text-gray-900 border-none outline-none focus:ring-2 focus:ring-apple-blue"
              >
                {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      {error && <p className="text-red-500 text-[13px]">{error}</p>}

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onClose}
          className="flex-1 py-2.5 rounded-xl text-[15px] font-medium bg-apple-lightgray text-gray-700 hover:bg-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={savePerson.isPending}
          className="flex-1 py-2.5 rounded-xl text-[15px] font-medium bg-apple-blue text-white hover:bg-blue-600 transition-colors disabled:opacity-50"
        >
          {savePerson.isPending ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Lead'}
        </button>
      </div>
    </form>
  )
}

function Field({
  label, value, onChange, type = 'text', required = false,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  required?: boolean
}) {
  return (
    <div>
      <label className="block text-[13px] text-apple-gray mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        className="w-full bg-apple-lightgray rounded-xl px-4 py-2.5 text-[15px] text-gray-900 border-none outline-none focus:ring-2 focus:ring-apple-blue placeholder:text-gray-400"
      />
    </div>
  )
}
