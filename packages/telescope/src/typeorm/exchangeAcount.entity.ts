import { Column, Entity, PrimaryColumn } from 'typeorm';

@Entity()
export class ExchangeAccount {
  @PrimaryColumn({ type: 'bigint', name: 'id' })
  id: number;

  @Column({ type: 'bigint' })
  exchange_id: number;

  @Column({ type: 'varchar', length: 255 })
  name: string;

  @Column({ type: 'varchar', length: 255 })
  api_key: string;
}
